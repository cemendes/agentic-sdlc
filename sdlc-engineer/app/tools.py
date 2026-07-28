import os
import shutil
import subprocess
import google.auth
from google.auth.transport.requests import Request

REPO_URL = "https://<YOUR_SOURCEMANAGER_INSTANCE>.sourcemanager.dev/<YOUR_PROJECT_ID>/sdlc-test-repo.git"
LOCAL_DIR = "/tmp/sdlc-test-repo"

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

def clone_repository() -> str:
    """Clones the Secure Source Manager Git repository to a local temporary directory.
    
    Returns:
        A status message indicating success or failure.
    """
    try:
        if os.path.exists(LOCAL_DIR):
            shutil.rmtree(LOCAL_DIR)
            
        token = _get_token()
        # Embed the OAuth2 token into the repository URL for basic authentication
        repo_url_with_auth = REPO_URL.replace("https://", f"https://oauth2:{token}@")
        cmd = [
            "git",
            "clone", repo_url_with_auth, LOCAL_DIR
        ]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            sa_email = "Local Dev / Non-Metadata Env"
            try:
                sa_email = requests.get("http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/email", headers={"Metadata-Flavor": "Google"}, timeout=2).text
            except Exception:
                pass
            return (f"Failed to clone repository (exit code {res.returncode}):\n"
                    f"Execution Identity: {sa_email}\n"
                    f"Token prefix: '{token[:12]}...' (length {len(token)})\n"
                    f"Stderr: {res.stderr}\nStdout: {res.stdout}")
            
        # Configure user name/email locally
        subprocess.run(["git", "config", "user.name", "Engineer Agent"], cwd=LOCAL_DIR)
        subprocess.run(["git", "config", "user.email", "engineer@example.com"], cwd=LOCAL_DIR)
        
        return "Repository successfully cloned."
    except Exception as e:
        return f"Exception during clone_repository: {type(e).__name__}: {str(e)}\n{traceback.format_exc()}"

def list_files() -> list[str]:
    """Lists all files in the cloned repository.
    
    Returns:
        A list of relative file paths in the repository, or error string in list if failed.
    """
    try:
        if not os.path.exists(LOCAL_DIR):
            return ["Error: Repository not cloned. Call clone_repository first."]
            
        files = []
        for root, _, filenames in os.walk(LOCAL_DIR):
            if ".git" in root:
                continue
            for filename in filenames:
                full_path = os.path.join(root, filename)
                rel_path = os.path.relpath(full_path, LOCAL_DIR)
                files.append(rel_path)
        return files
    except Exception as e:
        return [f"Exception during list_files: {str(e)}"]

def read_file(file_path: str) -> str:
    """Reads the contents of a file in the repository.
    
    Args:
        file_path: The relative path of the file to read.
        
    Returns:
        The content of the file.
    """
    try:
        full_path = os.path.join(LOCAL_DIR, file_path)
        if not os.path.exists(full_path):
            return f"Error: File {file_path} not found."
        with open(full_path, "r") as f:
            return f.read()
    except Exception as e:
        return f"Exception during read_file({file_path}): {str(e)}"

def write_file(file_path: str, content: str) -> str:
    """Writes or overwrites content to a file in the repository.
    
    Args:
        file_path: The relative path of the file.
        content: The content to write to the file.
        
    Returns:
        A success message.
    """
    try:
        full_path = os.path.join(LOCAL_DIR, file_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w") as f:
            f.write(content)
        return f"Successfully wrote to {file_path}."
    except Exception as e:
        return f"Exception during write_file({file_path}): {str(e)}"

def push_changes(branch_name: str, commit_message: str) -> str:
    """Creates a new git branch, commits local modifications, and pushes it to Secure Source Manager.
    
    Args:
        branch_name: The name of the new branch to create.
        commit_message: The git commit message.
        
    Returns:
        A success message with details of the branch pushed.
    """
    try:
        if not os.path.exists(LOCAL_DIR):
            return "Error: Repository not cloned. Call clone_repository first."
            
        # Branch, Commit, Push
        subprocess.run(["git", "checkout", "-B", branch_name], cwd=LOCAL_DIR)
        subprocess.run(["git", "add", "."], cwd=LOCAL_DIR)
        
        commit_res = subprocess.run(["git", "commit", "--allow-empty", "-m", commit_message], cwd=LOCAL_DIR, capture_output=True, text=True)
        if commit_res.returncode != 0 and "nothing to commit" not in commit_res.stdout and "nothing to commit" not in commit_res.stderr:
            return f"Failed to commit changes:\nStderr: {commit_res.stderr}\nStdout: {commit_res.stdout}"
        
        cmd = [
            "git",
            "push", "-u", "origin", branch_name
        ]
        push_res = subprocess.run(cmd, cwd=LOCAL_DIR, capture_output=True, text=True)
        if push_res.returncode != 0:
            return f"Failed to push branch to Secure Source Manager:\nStderr: {push_res.stderr}\nStdout: {push_res.stdout}"
            
        return f"Successfully created and pushed branch {branch_name} to Secure Source Manager."
    except Exception as e:
        return f"Exception during push_changes({branch_name}): {type(e).__name__}: {str(e)}\n{traceback.format_exc()}"

def delete_branch(branch_name: str) -> str:
    """Deletes a git branch both locally and remotely from Secure Source Manager.
    
    Args:
        branch_name: The name of the branch to delete.
        
    Returns:
        A success message indicating the branch was deleted.
    """
    try:
        token = _get_token()
        repo_url_with_auth = REPO_URL.replace("https://", f"https://oauth2:{token}@")
        
        if not os.path.exists(LOCAL_DIR):
            clone_repository()
        else:
            subprocess.run(["git", "remote", "set-url", "origin", repo_url_with_auth], cwd=LOCAL_DIR)
            
        # Switch to main branch first before deleting
        subprocess.run(["git", "checkout", "main"], cwd=LOCAL_DIR)
        
        # Delete local branch if it exists
        subprocess.run(["git", "branch", "-D", branch_name], cwd=LOCAL_DIR)
        
        # Delete remote branch using authenticated URL
        cmd = [
            "git",
            "push", repo_url_with_auth, "--delete", branch_name
        ]
        res = subprocess.run(cmd, cwd=LOCAL_DIR, capture_output=True, text=True)
        if res.returncode != 0 and "remote ref does not exist" not in res.stderr and "find ref" not in res.stderr and "not found" not in res.stderr:
            return f"Failed to delete remote branch:\nStderr: {res.stderr}\nStdout: {res.stdout}"
            
        return f"Successfully deleted branch {branch_name} locally and remotely."
    except Exception as e:
        return f"Exception during delete_branch({branch_name}): {str(e)}"
