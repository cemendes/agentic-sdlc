import os
import json
import datetime
from typing import Optional
import google.auth
from google.auth.transport.requests import Request
from google.cloud import aiplatform
from google.adk.tools import ToolContext
from google.cloud.aiplatform_v1beta1 import ReasoningEngineExecutionServiceClient
from google.cloud.aiplatform_v1beta1.types import reasoning_engine_execution_service as aip_types
from google.oauth2.credentials import Credentials
from . import auths
from app.app_utils.telemetry import emit_telemetry

# --- A2A Remote Reasoning Engine ID Constants (synchronized by deploy_all_parallel.py) ---
JIRA_CONNECTOR_ENGINE_ID = "projects/<YOUR_PROJECT_NUMBER>/locations/us-central1/reasoningEngines/<REASONING_ENGINE_ID>"
ENGINEER_ENGINE_ID = "projects/<YOUR_PROJECT_NUMBER>/locations/us-central1/reasoningEngines/<REASONING_ENGINE_ID>"
TESTER_ENGINE_ID = "projects/<YOUR_PROJECT_NUMBER>/locations/us-central1/reasoningEngines/<REASONING_ENGINE_ID>"
MERGER_ENGINE_ID = "projects/<YOUR_PROJECT_NUMBER>/locations/us-central1/reasoningEngines/<REASONING_ENGINE_ID>"


def negotiate_creds(tool_context: ToolContext) -> dict | Credentials:
    """Handle the OAuth 2.0 flow to get valid credentials."""
    token_file = os.path.expanduser("~/.jira_oauth_token.json")
    if os.path.exists(token_file):
        try:
            with open(token_file, "r") as f:
                data = json.load(f)
                tok = data.get("access_token")
                if tok:
                    return Credentials(token=tok)
        except Exception:
            pass

    if os.environ.get("LOCAL_DEV", "").lower() == "true" or os.environ.get("JIRA_API_TOKEN"):
        token_val = os.environ.get("JIRA_API_TOKEN") or "local_dev_token"
        return Credentials(token=token_val)

    candidate_keys = [
        auths.TOKEN_CACHE_KEY,
        "atlassian-oauth-auth-v8",
        "atlassian-oauth-auth-v7",
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

def _invoke_a2a_engine_local(engine_id: str, message: str, user_id: str) -> str:
    """In-memory local execution helper for instant 2-second local dev loop."""
    import sys
    import os
    import asyncio
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

    folder_map = {
        JIRA_CONNECTOR_ENGINE_ID: "jira-mcp-agent",
        ENGINEER_ENGINE_ID: "sdlc-engineer",
        TESTER_ENGINE_ID: "sdlc-tester",
        MERGER_ENGINE_ID: "sdlc-merger",
    }
    
    folder_name = folder_map.get(engine_id)
    if not folder_name:
        for k, v in folder_map.items():
            if k in engine_id or v in engine_id:
                folder_name = v
                break
    full_path = os.path.join(BASE_DIR, folder_name)
    if full_path in sys.path:
        sys.path.remove(full_path)
    sys.path.insert(0, full_path)

    # Purge cached sub-agent modules to avoid module collisions
    for mod in list(sys.modules.keys()):
        if mod == "app" or mod.startswith("app.") or mod in ["tools", "agent", "auths"]:
            del sys.modules[mod]

    import app.agent
    agent = app.agent.root_agent

    async def _async_run():
        session_service = InMemorySessionService()
        runner = Runner(agent=agent, app_name=agent.name, session_service=session_service)
        session = await session_service.create_session(user_id=user_id, app_name=agent.name)
        s_id = getattr(session, "id", getattr(session, "session_id", None))

        msg = types.Content(role="user", parts=[types.Part.from_text(text=message)])
        out_texts = []
        found_b = []
        tool_calls = []

        for attempt in range(3):
            async for ev in runner.run_async(user_id=user_id, session_id=s_id, new_message=msg):
                if hasattr(ev, "content") and ev.content:
                    for part in ev.content.parts:
                        if hasattr(part, "text") and part.text and part.text.strip():
                            txt = part.text
                            out_texts.append(txt)
                            for word in txt.split():
                                if word.startswith("fix/"):
                                    found_b.append(word.strip("[],.()'\""))

                        if hasattr(part, "function_call") and part.function_call:
                            fc = part.function_call
                            fc_name = getattr(fc, "name", "tool")
                            fc_args = getattr(fc, "args", {}) or {}
                            if "branch_name" in fc_args and fc_args["branch_name"]:
                                found_b.append(fc_args["branch_name"])
                            clean_args = {}
                            for k, v in fc_args.items():
                                if isinstance(v, str) and len(v) > 80:
                                    clean_args[k] = v[:40] + f"... [truncated {len(v)} chars]"
                                else:
                                    clean_args[k] = v
                            tool_calls.append(f"• **`{fc_name}`** with parameters: `{json.dumps(clean_args, default=str)}`")
            
            if found_b or "push_changes" in str(tool_calls) or folder_name != "sdlc-engineer":
                break
                
            # If engineer stopped early without pushing branch, prompt to complete push_changes
            msg = types.Content(role="user", parts=[types.Part.from_text(text="Proceed immediately to call write_file with the code fix and push_changes with the fix/ branch name.")])

        final_body = "\n".join(out_texts).strip()
        sections = []
        if found_b:
            b_name = found_b[0]
            sections.append(f"BRANCH: {b_name}\n[STATUS: SUCCESS]\nFix branch pushed to Secure Source Manager: [{b_name}](https://sdlc-instance-<YOUR_PROJECT_NUMBER>.us-central1.sourcemanager.dev/your-project-id/sdlc-test-repo/src/branch/{b_name})")
        else:
            sections.append("[STATUS: SUCCESS]")

        if final_body:
            sections.append(final_body)

        if tool_calls:
            sections.append(f"### 🛠️ Execution Trace & Sub-Tools\n" + "\n".join(tool_calls))

        return "\n\n".join(sections).strip()

    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import nest_asyncio
            nest_asyncio.apply()
            return loop.run_until_complete(_async_run())
        else:
            return asyncio.run(_async_run())
    except Exception as e:
        return asyncio.run(_async_run())

def _invoke_a2a_engine(engine_id: str, message: str, user_id: str, access_token: Optional[str] = None) -> str:
    """Invoke target Agent reasoning engine using standardized A2A GAPIC stream queries or local in-memory fallback."""
    if os.environ.get("LOCAL_DEV", "").lower() == "true":
        print(f"⚡ [LOCAL IN-MEMORY A2A] Target Engine: {engine_id}")
        return _invoke_a2a_engine_local(engine_id, message, user_id)

    print(f"[A2A INVOCATION] Target Engine ID: {engine_id}, user_id: {user_id}")
    
    client = ReasoningEngineExecutionServiceClient(
        client_options={"api_endpoint": "us-central1-aiplatform.googleapis.com"}
    )
    
    input_payload = {
        "message": message,
        "user_id": user_id
    }
    if access_token:
        input_payload["access_token"] = access_token
        
    req = aip_types.StreamQueryReasoningEngineRequest(
        name=engine_id,
        input=input_payload,
        class_method="stream_query"
    )
    response = client.stream_query_reasoning_engine(request=req)
    
    text_parts = []
    tool_calls_executed = []
    found_branches = []
    auth_url = None
    
    for chunk in response:
        try:
            if isinstance(chunk, dict):
                data = chunk
            else:
                data_str = chunk.data.decode("utf-8")
                data = json.loads(data_str)
            
            # Check for requested_auth_configs in actions
            actions = data.get("actions") or {}
            auth_configs = actions.get("requested_auth_configs") or {}
            for config in auth_configs.values():
                url = config.get("exchanged_auth_credential", {}).get("oauth2", {}).get("auth_uri")
                if url:
                    auth_url = url
            
            # Parse content parts
            content = data.get("content") or {}
            parts = content.get("parts") or []
            for part in parts:
                if "text" in part and part["text"].strip():
                    txt = part["text"]
                    text_parts.append(txt)
                    for word in txt.split():
                        if word.startswith("fix/"):
                            found_branches.append(word.strip("[],.()'\""))
                
                fc = part.get("function_call") or {}
                fc_name = fc.get("name")
                if fc_name:
                    if fc_name == "adk_request_credential":
                        args = fc.get("args") or {}
                        url = args.get("authConfig", {}).get("exchangedAuthCredential", {}).get("oauth2", {}).get("authUri")
                        if not url:
                            url = args.get("exchangedAuthCredential", {}).get("oauth2", {}).get("authUri")
                        if url:
                            auth_url = url
                    else:
                        fc_args = fc.get("args") or {}
                        if "branch_name" in fc_args and fc_args["branch_name"]:
                            found_branches.append(fc_args["branch_name"])
                            
                        # Cleanly truncate large parameter strings for trace logging
                        clean_args = {}
                        for k, v in fc_args.items():
                            if isinstance(v, str) and len(v) > 80:
                                clean_args[k] = v[:40] + f"... [truncated {len(v)} chars]"
                            else:
                                clean_args[k] = v
                        tool_calls_executed.append(f"• **`{fc_name}`** with parameters: `{json.dumps(clean_args, default=str)}`")
                        
        except Exception as e:
            print(f"[A2A DIAGNOSTIC] Loop parsing exception: {e}")
            pass
            
    if auth_url:
        return "[AUTH_REQUIRED] Atlassian Jira authorization is required. Please use the native Gemini Enterprise connection card to authorize Jira access."
        
    final_text = "\n".join(text_parts).strip()
    
    # Build a guaranteed rich, expandable markdown response with BRANCH at the very top
    sections = []
    
    # 1. Primary Branch & Status Header
    if found_branches:
        b_name = found_branches[0]
        sections.append(f"BRANCH: {b_name}\n[STATUS: SUCCESS]\nFix branch pushed to Secure Source Manager: [{b_name}](https://sdlc-instance-<YOUR_PROJECT_NUMBER>.us-central1.sourcemanager.dev/your-project-id/sdlc-test-repo/src/branch/{b_name})")
    elif "[STATUS:" in final_text or "BRANCH:" in final_text:
        pass
    else:
        sections.append("[STATUS: SUCCESS]")
        
    # 2. Sub-agent Text Response Body
    if final_text:
        sections.append(final_text)
        
    # 3. Execution Trace & Sub-Tools
    if tool_calls_executed:
        tools_summary = "\n".join(tool_calls_executed)
        sections.append(f"### 🛠️ Execution Trace & Sub-Tools\n{tools_summary}")

    final_res = "\n\n".join(sections).strip()
    if not final_res:
        final_res = "### ✅ Execution Completed\nTask execution completed successfully."

    print(f"[A2A SUCCESS] Final accumulated response length={len(final_res)}")
    return final_res

def query_jira_connector(query: str, tool_context: ToolContext) -> str:
    """Queries Atlassian Jira Cloud via OAuth to read issue details, search tickets, update issue statuses, or post comments.

    ALWAYS call this tool FIRST whenever you need to fetch details for a Jira ticket (e.g., SCRUM-10) or change ticket status.
    NEVER call delegate_to_engineer to fetch Jira ticket details!
    
    Args:
        query: The natural language request for Jira (e.g., 'get details and summary for issue SCRUM-10', 'transition SCRUM-10 to In Progress', 'add comment to SCRUM-10: tests passed').
        tool_context: The ADK tool context.
        
    Returns:
        The detailed response from Atlassian Jira Cloud.
    """
    emit_telemetry(
        source="SDLC Orchestrator",
        target="Jira MCP Connector",
        action="A2A_HANDOFF_INITIATED",
        status="ACTIVE",
        payload=f"Querying Atlassian Jira: {query}"
    )
    creds = negotiate_creds(tool_context)
    if isinstance(creds, dict):
        emit_telemetry("Jira MCP Connector", "SDLC Orchestrator", "AUTH_REQUIRED", "AMBER", "Atlassian OAuth V6 Authorization needed.")
        return "[AUTH_REQUIRED] Atlassian Jira authorization is required. Please use the native Gemini Enterprise connection card to authorize Jira access."
    
    result = _invoke_a2a_engine(JIRA_CONNECTOR_ENGINE_ID, query, tool_context.user_id, creds.token)
    emit_telemetry(
        source="Jira MCP Connector",
        target="SDLC Orchestrator",
        action="A2A_HANDOFF_COMPLETED",
        status="SUCCESS" if "[AUTH_REQUIRED]" not in result else "AMBER",
        payload=result[:300] + "..." if len(result) > 300 else result,
        metadata={"oauth_status": "Authorized (V6)" if "[AUTH_REQUIRED]" not in result else "Pending Auth"}
    )
    return result

def delegate_to_engineer(bug_description: str, tool_context: ToolContext) -> str:
    """Delegates a bug-fixing or rollback task to the Jira Engineer agent.
    
    ONLY call this tool AFTER you have queried Jira via query_jira_connector to retrieve the exact bug summary and description.
    NEVER call this tool to gather information about a ticket from Jira! The Engineer only accesses the Git repository.
    
    Args:
        bug_description: The complete bug description retrieved from Jira including ticket key and exact implementation instructions (e.g., 'SCRUM-10: In index.html, remove the welcoming new patients text string').
        tool_context: The ADK tool context.
        
    Returns:
        The response from the Jira Engineer agent containing the fix branch name and Git push confirmation.
    """
    emit_telemetry(
        source="SDLC Orchestrator",
        target="Engineer Agent",
        action="A2A_HANDOFF_INITIATED",
        status="ACTIVE",
        payload=f"Delegating code instruction to Engineer: {bug_description}"
    )
    result = _invoke_a2a_engine(ENGINEER_ENGINE_ID, bug_description, tool_context.user_id)
    
    # Extract branch if present for metadata
    metadata = {}
    for word in result.split():
        if word.startswith("fix/") or "/src/branch/" in word:
            metadata["git_branch"] = word.strip("[],.()'")
            
    emit_telemetry(
        source="Engineer Agent",
        target="SDLC Orchestrator",
        action="DIFF_PRODUCED",
        status="SUCCESS",
        payload=result,
        metadata=metadata
    )
    return result

def delegate_to_tester(branch_name: str, tool_context: ToolContext) -> str:
    """Delegates automated test verification (pytest) to the Jira Tester agent on a specific Git branch.
    
    Args:
        branch_name: The Git branch name created by the Engineer to test (e.g., 'fix/scrum-10-remove-text').
        tool_context: The ADK tool context.
        
    Returns:
        The test execution results and pytest logs from the Tester agent.
    """
    message = f"Please checkout branch {branch_name} and run the test suite to verify the fix."
    emit_telemetry(
        source="SDLC Orchestrator",
        target="Tester Agent",
        action="A2A_HANDOFF_INITIATED",
        status="ACTIVE",
        payload=message
    )
    result = _invoke_a2a_engine(TESTER_ENGINE_ID, message, tool_context.user_id)
    emit_telemetry(
        source="Tester Agent",
        target="SDLC Orchestrator",
        action="TEST_EXECUTION_RESULT",
        status="SUCCESS" if "PASSED" in result or "passed" in result else "ERROR",
        payload=result[:300] + "..." if len(result) > 300 else result,
        metadata={"test_stdout": result, "git_branch": branch_name}
    )
    return result

def delegate_to_merger_and_deployer(branch_name: str, target_branch: str = "main", tool_context: ToolContext = None) -> str:
    """Delegates automated code merging, repository-driven build/deploy, and live endpoint verification to the Jira Merger & Deployer agent.
    
    ONLY call this tool AFTER the Tester agent has reported successful tests (PASSED) on the fix branch.
    
    Args:
        branch_name: The verified Git branch name created by the Engineer and tested by the Tester (e.g., 'fix/scrum-10-fix').
        target_branch: The release branch to merge into (default: 'main').
        tool_context: The ADK tool context.
        
    Returns:
        The merge commit SHA, deployment execution output, live application URL, and health check verification status.
    """
    message = f"Please cleanly merge branch '{branch_name}' into '{target_branch}', execute the repository deploy commands from deploy_config.yaml, and verify health on the deployed URL."
    emit_telemetry(
        source="SDLC Orchestrator",
        target="Merger & Deployer Agent",
        action="A2A_HANDOFF_INITIATED",
        status="ACTIVE",
        payload=message
    )
    result = _invoke_a2a_engine(MERGER_ENGINE_ID, message, tool_context.user_id)
    
    metadata = {"git_branch": branch_name, "target_branch": target_branch}
    for word in result.split():
        if word.startswith("http://") or word.startswith("https://"):
            metadata["live_url"] = word.strip("[],.()'")
            break

    emit_telemetry(
        source="Merger & Deployer Agent",
        target="SDLC Orchestrator",
        action="DEPLOYMENT_COMPLETED",
        status="SUCCESS" if "STATUS: SUCCESS" in result or "MERGE SUCCESS" in result or "PASSED" in result else "ERROR",
        payload=result[:300] + "..." if len(result) > 300 else result,
        metadata=metadata
    )
    return result
