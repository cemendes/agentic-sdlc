import os
import google.auth
try:
    import urllib3.contrib.pyopenssl
    urllib3.contrib.pyopenssl.extract_from_urllib3()
except Exception:
    pass
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from .tools import (
    search_jira_tickets, 
    create_jira_ticket,
    list_projects,
    get_issue_details,
    get_issue_comments,
    add_comment,
    transition_issue
)

try:
    _, project_id = google.auth.default()
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id or ""
except Exception:
    pass
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

# Define the root agent
root_agent = Agent(
    name="jira_agent",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are a helpful Jira assistant. Your goal is to help the user read and manage Jira tickets.\n"
        "When the user asks you to read or create tickets, you will use your provided Jira tools.\n"
        "Because these tools require authentication, you may receive a dictionary with 'pending': True.\n"
        "If and ONLY if you receive 'pending': True, DO NOT apologize "
        "or explain the technical details. Simply tell the user to please check the browser or complete "
        "the authorization flow to proceed, and stop there.\n"
        "If you receive a standard API error from Jira (e.g., invalid project key), explain the error to the user and ask them for the correct information (like the project key)."
    ),
    tools=[
        search_jira_tickets, 
        create_jira_ticket,
        list_projects,
        get_issue_details,
        get_issue_comments,
        add_comment,
        transition_issue
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
