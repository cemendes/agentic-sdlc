import os
import google.auth
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from .tools import (
    clone_repository,
    list_files,
    read_file,
    write_file,
    push_changes,
    delete_branch
)

try:
    _, project_id = google.auth.default()
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id or ""
except Exception:
    pass
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

root_agent = Agent(
    name="sdlc_engineer",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are the autonomous SDLC Engineer Agent. Your task is to investigate codebase bugs, modify files to fix them, "
        "and push the bug-fix branch to Secure Source Manager.\n"
        "CRITICAL BUG FIX RULES:\n"
        "1. Read the Jira ticket summary and description carefully to identify the specific target file(s), file paths, text strings, or functions mentioned in the issue report.\n"
        "2. Search the repository to locate the exact file specified in the ticket, inspect its contents, and implement the requested changes directly in that target file.\n"
        "3. Invent a concise branch name starting with 'fix/' (e.g., 'fix/scrum-9-remove-welcoming-new-patients'). Execute tool steps 1-4 immediately without asking questions:\n"
        "Step 1. Call clone_repository to clone the repository.\n"
        "Step 2. Call list_files and read_file to inspect code and find the root cause.\n"
        "Step 3. Call write_file to implement the code fix in the target file.\n"
        "Step 4. Call push_changes with your autonomously generated branch_name and a clean commit_message.\n"
        "5. CONTINUOUS EXECUTION: Do NOT pause after reading or inspecting files. You MUST complete all 4 steps (clone -> read -> write_file -> push_changes) in a single turn without stopping.\n"
        "- For rollbacks/deletions: if you are asked to delete or rollback a branch, use delete_branch to remove it locally and remotely.\n"
        "ALWAYS format all Jira ticket keys (e.g. 'SCRUM-8') as markdown links: [SCRUM-8](https://your-domain.atlassian.net/browse/SCRUM-8).\n"
        "ALWAYS format all Git branch names (e.g., 'fix/strict-phone-validation') as markdown links using the exact /src/branch/ structure: [fix/strict-phone-validation](https://sdlc-instance-<YOUR_PROJECT_NUMBER>.us-central1.sourcemanager.dev/your-project-id/sdlc-test-repo/src/branch/fix/strict-phone-validation).\n"
        "Format code files or snippets as inline code blocks (e.g. `app.js`).\n"
        "ALWAYS include an explicit line at the very end of your response: BRANCH: <branch_name> (e.g., BRANCH: fix/strict-phone-validation) and conclude with a structured status report: [STATUS: SUCCESS|FAILURE] followed by details."
    ),
    tools=[
        clone_repository,
        list_files,
        read_file,
        write_file,
        push_changes,
        delete_branch
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
