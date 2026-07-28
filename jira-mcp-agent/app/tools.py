import datetime
import json
import logging
import os
import requests
from google.adk.tools import ToolContext
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from app.app_utils.config_helper import get_setting
from . import auths

logger = logging.getLogger(__name__)

def negotiate_creds(tool_context: ToolContext) -> dict | Credentials:
    """Handle the OAuth 2.0 flow to get valid credentials."""
    logger.info("Negotiating credentials using OAuth 2.0")

    token_file = os.path.expanduser("~/.jira_oauth_token.json")
    if os.path.exists(token_file):
        try:
            with open(token_file, "r") as f:
                data = json.load(f)
                tok = data.get("access_token")
                if tok:
                    return Credentials(token=tok)
        except Exception as e:
            logger.warning(f"Failed loading ~/.jira_oauth_token.json: {e}")

    if os.environ.get("LOCAL_DEV", "").lower() == "true" or os.environ.get("JIRA_API_TOKEN"):
        token_val = os.environ.get("JIRA_API_TOKEN") or "local_dev_token"
        return Credentials(token=token_val)

    # If the parent agent (Orchestrator) passed the access token via env, use it directly
    env_token = os.environ.get(f"JIRA_ACCESS_TOKEN_{tool_context.user_id}")
    if env_token:
        logger.info("Found token in environment variable passed from Orchestrator")
        return Credentials(token=env_token)

    candidate_keys = [
        auths.TOKEN_CACHE_KEY,
        "atlassian-oauth-auth-v6",
        "atlassian-oauth-auth-v5",
        "jira-oauth",
    ]
    
    cached_token = None
    if hasattr(tool_context, "state") and tool_context.state:
        for k in candidate_keys:
            val = tool_context.state.get(k) or tool_context.state.get(f"temp:{k}")
            if val:
                cached_token = val
                break
        if not cached_token:
            state_dict = tool_context.state.to_dict() if hasattr(tool_context.state, "to_dict") else (tool_context.state or {})
            for sk, sv in state_dict.items():
                if ("atlassian" in str(sk).lower() or "oauth" in str(sk).lower()) and sv:
                    cached_token = sv
                    break

    if cached_token:
        token_str = None
        if isinstance(cached_token, str):
            token_str = cached_token
        elif isinstance(cached_token, dict):
            token_str = cached_token.get("token") or cached_token.get("access_token")
            
        if token_str and isinstance(token_str, str) and not token_str.startswith("<"):
            return Credentials(token=token_str)

    if exchanged_creds := tool_context.get_auth_response(auths.AUTH_CONFIG):
        token_str = exchanged_creds.oauth2.access_token
        if token_str:
            tool_context.state[auths.TOKEN_CACHE_KEY] = token_str
            return Credentials(token=token_str)

    tool_context.request_credential(auths.AUTH_CONFIG)
    return {"pending": True, "message": "Awaiting user authentication"}

def get_cloud_id(access_token: str) -> str | None:
    """Fetch the Atlassian Cloud ID for the authenticated user."""
    if os.environ.get("JIRA_API_TOKEN"):
        return "local_direct"

    response = requests.get(
        "https://api.atlassian.com/oauth/token/accessible-resources",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
    )
    if response.status_code == 200:
        resources = response.json()
        if resources:
            target_url = get_setting("JIRA_SITE_URL", "").strip().rstrip("/")
            if target_url:
                for res in resources:
                    res_url = res.get("url", "").strip().rstrip("/")
                    if res_url == target_url:
                        logger.info(f"Matched Cloud ID for target URL {target_url}: {res['id']}")
                        return res["id"]
            logger.warning(f"No match found for JIRA_SITE_URL '{target_url}'. Falling back to first resource.")
            return resources[0]["id"]
    logger.error(f"Failed to fetch accessible resources: {response.text}")
    return None

def _get_jira_request_details(cloud_id: str, access_token: str, path: str):
    """Build URL and headers for Jira REST API requests (Basic Auth or OAuth)."""
    import base64
    jira_domain = get_setting("JIRA_SITE_URL", "https://your-domain.atlassian.net").strip().rstrip("/")
    api_token = os.environ.get("JIRA_API_TOKEN")
    email = os.environ.get("JIRA_USER_EMAIL", "user@example.com")
    
    if api_token or cloud_id == "local_direct":
        url = f"{jira_domain}/rest/api/3/{path.lstrip('/')}"
        auth_str = base64.b64encode(f"{email}:{api_token}".encode()).decode() if api_token else access_token
        auth_header = f"Basic {auth_str}" if api_token else f"Bearer {access_token}"
        headers = {
            "Authorization": auth_header,
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        return url, headers
    else:
        url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/{path.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        return url, headers

def _get_field_mapping(cloud_id: str, access_token: str, tool_context: ToolContext) -> dict:
    """Fetch and cache the mapping of custom field IDs to their human-readable names."""
    cache_key = f"jira_field_map_{cloud_id}"
    if cache_key in tool_context.state:
        return tool_context.state[cache_key]

    url, headers = _get_jira_request_details(cloud_id, access_token, "field")
    
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        field_data = response.json()
        field_map = {field["id"]: field["name"] for field in field_data}
        tool_context.state[cache_key] = field_map
        return field_map
    
    logger.error(f"Failed to fetch field mapping: {response.text}")
    return {}

def _translate_issue_fields(issue: dict, field_map: dict) -> dict:
    """Translate customfield_XXX keys in an issue's 'fields' dict to their human-readable names."""
    if "fields" not in issue or not field_map:
        return issue
        
    translated_fields = {}
    for key, value in issue["fields"].items():
        if key in field_map:
            translated_fields[field_map[key]] = value
        else:
            translated_fields[key] = value
            
    issue["fields"] = translated_fields
    return issue

def search_jira_tickets(jql: str, tool_context: ToolContext) -> dict:
    """Search for Jira tickets using JQL.
    
    Args:
        jql: The Jira Query Language string to search for issues.
    """
    creds = negotiate_creds(tool_context)
    if isinstance(creds, dict):
        return creds

    cloud_id = get_cloud_id(creds.token)
    if not cloud_id:
        return {"status": "error", "message": "Could not find accessible Jira instance."}

    url, headers = _get_jira_request_details(cloud_id, creds.token, "search/jql")
    payload = {
        "jql": jql,
        "maxResults": 10,
        "fields": ["*all"]
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 200:
        data = response.json()
        field_map = _get_field_mapping(cloud_id, creds.token, tool_context)
        if field_map and "issues" in data:
            for issue in data["issues"]:
                _translate_issue_fields(issue, field_map)
        logger.info(f"search_jira_tickets payload: {json.dumps(data)}")
        return {"status": "success", "data": data}
    return {"status": "error", "message": response.text}

def create_jira_ticket(project_key: str, summary: str, description: str, issue_type: str, tool_context: ToolContext) -> dict:
    """Create a new Jira ticket.
    
    Args:
        project_key: The key of the project (e.g. 'PROJ').
        summary: The title/summary of the issue.
        description: A detailed description of the issue.
        issue_type: The type of issue (e.g. 'Task', 'Bug', 'Story').
    """
    creds = negotiate_creds(tool_context)
    if isinstance(creds, dict):
        return creds

    cloud_id = get_cloud_id(creds.token)
    if not cloud_id:
        return {"status": "error", "message": "Could not find accessible Jira instance."}

    url, headers = _get_jira_request_details(cloud_id, creds.token, "issue")
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [
                    {
                        "type": "paragraph",
                        "content": [
                            {"type": "text", "text": description}
                        ]
                    }
                ]
            },
            "issuetype": {"name": issue_type}
        }
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        return {"status": "success", "data": response.json()}
    return {"status": "error", "message": response.text}

def list_projects(tool_context: ToolContext) -> dict:
    """Retrieve a list of all Jira projects the user has access to."""
    creds = negotiate_creds(tool_context)
    if isinstance(creds, dict):
        return creds

    cloud_id = get_cloud_id(creds.token)
    if not cloud_id:
        return {"status": "error", "message": "Could not find accessible Jira instance."}

    url = f"https://api.atlassian.com/ex/jira/{cloud_id}/rest/api/3/project"
    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Accept": "application/json"
    }

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return {"status": "success", "data": response.json()}
    return {"status": "error", "message": response.text}

def get_issue_details(issue_key: str, tool_context: ToolContext) -> dict:
    """Retrieve the full details of a specific Jira issue.
    
    Args:
        issue_key: The ID or key of the issue (e.g., SCRUM-2).
    """
    creds = negotiate_creds(tool_context)
    if isinstance(creds, dict):
        return creds

    cloud_id = get_cloud_id(creds.token)
    if not cloud_id:
        return {"status": "error", "message": "Could not find accessible Jira instance."}

    url, headers = _get_jira_request_details(cloud_id, creds.token, f"issue/{issue_key}")

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        field_map = _get_field_mapping(cloud_id, creds.token, tool_context)
        if field_map:
            _translate_issue_fields(data, field_map)
        logger.info(f"get_issue_details payload: {json.dumps(data)}")
        return {"status": "success", "data": data}
    return {"status": "error", "message": response.text}

def get_issue_comments(issue_key: str, tool_context: ToolContext) -> dict:
    """Retrieve all comments for a specific Jira issue.
    
    Args:
        issue_key: The ID or key of the issue.
    """
    creds = negotiate_creds(tool_context)
    if isinstance(creds, dict):
        return creds

    cloud_id = get_cloud_id(creds.token)
    if not cloud_id:
        return {"status": "error", "message": "Could not find accessible Jira instance."}

    url, headers = _get_jira_request_details(cloud_id, creds.token, f"issue/{issue_key}/comment")

    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return {"status": "success", "data": response.json()}
    return {"status": "error", "message": response.text}

def parse_inline_text(text: str) -> list[dict]:
    import re
    # Regex to split on markdown links, HTML anchors, bold, and code
    pattern = re.compile(r"(\[.*?\]\(.*?\))|(<a href=\".*?\" target=\"_blank\">.*?</a>)|(\*\*.*?\*\*)|(`.*?`)|(\*.*?\*)")
    parts = pattern.split(text)
    
    nodes = []
    for part in parts:
        if not part:
            continue
            
        # Parse Markdown Link: [text](url)
        link_match = re.match(r"^\[(.*?)\]\((.*?)\)$", part)
        if link_match:
            nodes.append({
                "type": "text",
                "text": link_match.group(1),
                "marks": [
                    {
                        "type": "link",
                        "attrs": {
                            "href": link_match.group(2)
                        }
                    }
                ]
            })
            continue
            
        # Parse HTML Link: <a href="url" target="_blank">text</a>
        html_match = re.match(r"^<a href=\"(.*?)\" target=\"_blank\">(.*?)</a>$", part)
        if html_match:
            nodes.append({
                "type": "text",
                "text": html_match.group(2),
                "marks": [
                    {
                        "type": "link",
                        "attrs": {
                            "href": html_match.group(1)
                        }
                    }
                ]
            })
            continue
            
        # Parse Inline Code: `code`
        if part.startswith("`") and part.endswith("`"):
            nodes.append({
                "type": "text",
                "text": part[1:-1],
                "marks": [{"type": "code"}]
            })
            continue
            
        # Parse Bold: **bold**
        if part.startswith("**") and part.endswith("**"):
            nodes.append({
                "type": "text",
                "text": part[2:-2],
                "marks": [{"type": "strong"}]
            })
            continue
            
        # Parse Italic/Bold: *bold*
        if part.startswith("*") and part.endswith("*"):
            nodes.append({
                "type": "text",
                "text": part[1:-1],
                "marks": [{"type": "strong"}]
            })
            continue
            
        # Normal Text
        nodes.append({
            "type": "text",
            "text": part
        })
        
    if not nodes:
        nodes.append({
            "type": "text",
            "text": text
        })
    return nodes

def comment_to_adf(comment_text: str) -> dict:
    # Normalize real or escaped newlines
    comment_text = comment_text.replace("\\n", "\n")
    blocks = comment_text.split("\n\n")
    content_nodes = []
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
            
        lines = block.split("\n")
        paragraph_content = []
        for i, line in enumerate(lines):
            if i > 0:
                paragraph_content.append({"type": "hardBreak"})
            
            # Parse inline styles for the current line
            paragraph_content.extend(parse_inline_text(line))
            
        content_nodes.append({
            "type": "paragraph",
            "content": paragraph_content
        })
        
    return {
        "type": "doc",
        "version": 1,
        "content": content_nodes
    }

def add_comment(issue_key: str, comment_text: str, tool_context: ToolContext) -> dict:
    """Add a new comment to a Jira issue.
    
    Args:
        issue_key: The ID or key of the issue.
        comment_text: The plaintext comment to add.
    """
    creds = negotiate_creds(tool_context)
    if isinstance(creds, dict):
        return creds

    cloud_id = get_cloud_id(creds.token)
    if not cloud_id:
        return {"status": "error", "message": "Could not find accessible Jira instance."}

    url, headers = _get_jira_request_details(cloud_id, creds.token, f"issue/{issue_key}/comment")
    payload = {
        "body": comment_to_adf(comment_text)
    }

    response = requests.post(url, headers=headers, json=payload)
    if response.status_code == 201:
        return {"status": "success", "data": response.json()}
    return {"status": "error", "message": response.text}

def transition_issue(issue_key: str, transition_name: str, tool_context: ToolContext) -> dict:
    """Transition an issue to a new status (e.g., 'In Progress', 'Done').
    
    Args:
        issue_key: The ID or key of the issue.
        transition_name: The human-readable name of the target transition/status.
    """
    creds = negotiate_creds(tool_context)
    if isinstance(creds, dict):
        return creds

    cloud_id = get_cloud_id(creds.token)
    if not cloud_id:
        return {"status": "error", "message": "Could not find accessible Jira instance."}

    trans_url, headers = _get_jira_request_details(cloud_id, creds.token, f"issue/{issue_key}/transitions")
    response = requests.get(trans_url, headers=headers)
    if response.status_code != 200:
        return {"status": "error", "message": f"Failed to get available transitions: {response.text}"}
    
    transitions = response.json().get("transitions", [])
    target_transition = next((t for t in transitions if t["name"].lower() == transition_name.lower()), None)
    
    if not target_transition:
        valid_names = [t["name"] for t in transitions]
        return {
            "status": "error", 
            "message": f"Invalid transition '{transition_name}'. Available options: {', '.join(valid_names)}"
        }
        
    payload = {"transition": {"id": target_transition["id"]}}
    post_response = requests.post(trans_url, headers=headers, json=payload)
    if post_response.status_code in [200, 204]:
        return {"status": "success", "message": f"Successfully transitioned issue {issue_key} to '{transition_name}'."}
    return {"status": "error", "message": post_response.text}
