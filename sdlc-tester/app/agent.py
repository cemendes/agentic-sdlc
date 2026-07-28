import os
import google.auth
from google.adk.agents import Agent
from google.adk.apps import App
from google.adk.models import Gemini
from google.genai import types

from .tools import (
    clone_and_checkout,
    run_tests,
    run_bash_command
)

try:
    _, project_id = google.auth.default()
    os.environ["GOOGLE_CLOUD_PROJECT"] = project_id or ""
except Exception:
    pass
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"

root_agent = Agent(
    name="sdlc_tester",
    model=Gemini(
        model="gemini-2.5-flash",
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are the SDLC Tester Agent. Your task is to validate code modifications (git branches) "
        "created by the Engineer Agent by running tests in a secure environment.\n"
        "When the Orchestrator delegates a validation task to you, you should:\n"
        "1. Clone the repository and checkout the specified branch using clone_and_checkout.\n"
        "2. Run pytest using run_tests to check if unit tests pass.\n"
        "3. If needed, execute custom verification commands using run_bash_command.\n"
        "4. Return the test results (stdout, stderr, exit code) back to the Orchestrator.\n"
        "5. ALWAYS format any Jira ticket references (e.g. 'SCRUM-8') as clickable hyperlinks pointing to: <a href=\"https://your-domain.atlassian.net/browse/SCRUM-8\" target=\"_blank\">SCRUM-8</a>.\n"
        "6. ALWAYS format all Git branch references (e.g., 'fix/strict-phone-validation') as clickable hyperlinks pointing to: <a href=\"https://sdlc-instance-<YOUR_PROJECT_NUMBER>.us-central1.sourcemanager.dev/your-project-id/sdlc-test-repo/tree/fix/strict-phone-validation\" target=\"_blank\">fix/strict-phone-validation</a>.\n"
        "7. Conclude your final response with a structured status report in this format: [STATUS: SUCCESS|FAILURE] followed by details (e.g. tests passed/failed count, compilation error messages)."
    ),
    tools=[
        clone_and_checkout,
        run_tests,
        run_bash_command
    ],
)

app = App(
    root_agent=root_agent,
    name="app",
)
