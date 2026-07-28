import os
import shutil
import subprocess
import google.auth
from google.auth.transport.requests import Request

REPO_URL = "https://<YOUR_SOURCEMANAGER_INSTANCE>.sourcemanager.dev/<YOUR_PROJECT_ID>/sdlc-test-repo.git"
LOCAL_DIR = "/tmp/sdlc-test-repo-tester"

import traceback
import requests

def _get_token() -> str:
    # 1. Query GCE/Cloud Run metadata server directly inside container environments
    try:
        url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"
        headers = {"Metadata-Flavor": "Google"}
        res = requests.get(url, headers=headers, timeout=2)
        if res.status_code == 200:
            token_data = res.json()
            access_token = token_data.get("access_token")
            if access_token and isinstance(access_token, str) and not access_token.startswith("<"):
                return access_token
    except Exception:
        pass

    # 2. Fallback to SDK default (for local dev workstation environments)
    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/cloud-platform"])
    credentials.refresh(Request())
    token = getattr(credentials, "token", None)
    if not token or str(token).startswith("<"):
        raise ValueError(f"Could not extract valid string token from credentials object: {credentials}")
    return str(token)

def clone_and_checkout(branch_name: str) -> str:
    """Clones the Secure Source Manager repository and checks out the specified branch.
    
    Args:
        branch_name: The Git branch name to test.
        
    Returns:
        A success message indicating the branch was checked out.
    """
    try:
        if os.path.exists(LOCAL_DIR):
            shutil.rmtree(LOCAL_DIR)
            
        token = _get_token()
        repo_url_with_auth = REPO_URL.replace("https://", f"https://oauth2:{token}@")
        cmd = [
            "git",
            "clone", "--branch", branch_name, repo_url_with_auth, LOCAL_DIR
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            sa_email = "Local Dev / Non-Metadata Env"
            try:
                sa_email = requests.get("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email", headers={"Metadata-Flavor": "Google"}, timeout=2).text
            except Exception:
                pass
            return (f"Failed to clone and checkout branch {branch_name}:\n"
                    f"Execution Identity: {sa_email}\n"
                    f"Token prefix: '{token[:12]}...' (length {len(token)})\n"
                    f"Stderr: {res.stderr}\nStdout: {res.stdout}")
        return f"Successfully cloned and checked out branch {branch_name}."
    except Exception as e:
        return f"Exception during clone_and_checkout({branch_name}): {type(e).__name__}: {str(e)}\n{traceback.format_exc()}"

def run_tests() -> dict:
    """Runs pytest on the checked-out codebase and returns the results.
    
    Returns:
        A dictionary containing exit_code, stdout, and stderr from pytest.
    """
    try:
        if not os.path.exists(LOCAL_DIR):
            return {"exit_code": -1, "stdout": "", "stderr": "Error: Repository not cloned. Call clone_and_checkout first."}
            
        res = subprocess.run(["python3", "-m", "pytest"], cwd=LOCAL_DIR, capture_output=True, text=True)
        return {
            "exit_code": res.returncode,
            "stdout": res.stdout,
            "stderr": res.stderr
        }
    except Exception as e:
        return {"exit_code": -1, "stdout": "", "stderr": f"Exception running tests: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}"}

def run_bash_command(command: str) -> str:
    """Executes a custom bash command inside the repository directory.
    
    Args:
        command: The bash command string to execute.
        
    Returns:
        The output (stdout/stderr merged) of the command.
    """
    try:
        if not os.path.exists(LOCAL_DIR):
            return "Error: Repository not cloned. Call clone_and_checkout first."
            
        res = subprocess.run(command, shell=True, cwd=LOCAL_DIR, capture_output=True, text=True)
        return f"Exit Code: {res.returncode}\nOutput:\n{res.stdout}\n{res.stderr}"
    except Exception as e:
        return f"Exception executing bash command '{command}': {str(e)}"
