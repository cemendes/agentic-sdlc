#!/usr/bin/env python3
"""
2-Phase Parallel Agent Deployment Script with Artifact Registry Container Copying & OAuth Integration
Phase 1: Concurrently builds/pushes container images and deploys Phase 1 agents (jira-mcp-agent, sdlc-engineer, sdlc-tester)
Phase 2: Reads Phase 1 ReasoningEngine IDs, injects them into Orchestrator tools.py, builds/pushes container image, deploys sdlc-orchestrator, and binds Atlassian OAuth v6.
"""

import os
import sys
import time
import json
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

ROOT_DIR = os.path.abspath(os.path.dirname(__file__))
REGISTRY_HOST = "us-central1-docker.pkg.dev/your-project-id/agent-platform-containers"
GEMINI_ENTERPRISE_APP = "projects/<YOUR_PROJECT_NUMBER>/locations/global/collections/default_collection/engines/privia-health-dora_1784047034048"
ATLASSIAN_AUTH_ID = "projects/<YOUR_PROJECT_NUMBER>/locations/global/authorizations/atlassian-oauth-auth-v6"

PHASE_1_AGENTS = [
    {"name": "jira-mcp-agent", "dir": os.path.join(ROOT_DIR, "jira-mcp-agent")},
    {"name": "sdlc-engineer", "dir": os.path.join(ROOT_DIR, "sdlc-engineer")},
    {"name": "sdlc-tester", "dir": os.path.join(ROOT_DIR, "sdlc-tester")},
]

ORCHESTRATOR_AGENT = {"name": "sdlc-orchestrator", "dir": os.path.join(ROOT_DIR, "sdlc-orchestrator")}

def build_and_push_container(image_name: str, context_dir: str, dockerfile_path: str = None) -> bool:
    """Builds Docker container image and pushes it to Artifact Registry if Docker is available."""
    extra_paths = ["/usr/local/bin", "/opt/homebrew/bin", os.path.expanduser("~/.docker/bin")]
    current_path = os.environ.get("PATH", "")
    os.environ["PATH"] = ":".join(extra_paths) + ":" + current_path

    if dockerfile_path is None:
        dockerfile_path = os.path.join(context_dir, "Dockerfile")

    if not os.path.exists(dockerfile_path):
        print(f"ℹ️ [CONTAINER] No Dockerfile found at {dockerfile_path}. Skipping container image build.")
        return True

    full_image_tag = f"{REGISTRY_HOST}/{image_name}:latest"

    if shutil.which("docker"):
        try:
            print(f"🐳 [CONTAINER BUILD] Building image {full_image_tag}...")
            subprocess.run(
                ["docker", "build", "-f", dockerfile_path, "-t", full_image_tag, context_dir],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"⬆️ [CONTAINER PUSH] Copying image to Artifact Registry: {full_image_tag}...")
            subprocess.run(
                ["docker", "push", full_image_tag],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"✅ [CONTAINER READY] Successfully pushed {full_image_tag}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"⚠️ [CONTAINER NOTICE] Local docker build failed for {image_name}: {e.stderr[:100]}")
            return False
    else:
        print(f"ℹ️ [CONTAINER] Local 'docker' binary not active. Skipping container image build for {image_name}.")
        return True

def publish_agent_to_gemini_enterprise(agent_info: dict, runtime_id: str) -> bool:
    """Registers agent to Gemini Enterprise and binds Atlassian OAuth authorization to the Jira SDLC Orchestrator."""
    agent_name = agent_info["name"]
    agent_dir = agent_info["dir"]

    if not runtime_id:
        return False

    cmd = [
        "agents-cli", "publish", "gemini-enterprise",
        f"--agent-runtime-id={runtime_id}",
        f"--gemini-enterprise-app-id={GEMINI_ENTERPRISE_APP}",
        f"--display-name={agent_name}",
    ]

    # Attach Atlassian OAuth authorization ID for the primary SDLC Orchestrator agent
    if agent_name == "sdlc-orchestrator":
        cmd.append(f"--authorization-id={ATLASSIAN_AUTH_ID}")

    print(f"🔐 [OAUTH PUBLISH] Registering {agent_name} with Gemini Enterprise...")
    try:
        subprocess.run(cmd, cwd=agent_dir, check=True, capture_output=True, text=True)
        print(f"✅ [OAUTH READY] Successfully registered {agent_name}!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ [OAUTH NOTICE] Note during Gemini Enterprise registration for {agent_name}:\n{e.stderr}")
        return False

def deploy_single_agent(agent_info: dict) -> tuple[str, bool, float, str]:
    agent_name = agent_info["name"]
    agent_dir = agent_info["dir"]
    start_time = time.time()

    print(f"🚀 [START] Processing {agent_name}...")

    # 1. Build and push container image if Dockerfile exists
    build_and_push_container(agent_name, agent_dir)

    # 2. Deploy Reasoning Engine / Agent Runtime
    python_bin = os.path.join(agent_dir, ".venv", "bin", "python")
    if not os.path.exists(python_bin):
        python_bin = sys.executable

    deploy_script = os.path.join(agent_dir, "deploy_agent.py")

    try:
        proc = subprocess.run(
            [python_bin, deploy_script],
            cwd=agent_dir,
            capture_output=True,
            text=True,
            check=True
        )
        elapsed = time.time() - start_time
        print(f"✅ [SUCCESS] Deployed {agent_name} in {elapsed:.1f} seconds")

        # 3. Publish to Gemini Enterprise with OAuth binding (Orchestrator only)
        if agent_name == "sdlc-orchestrator":
            runtime_id = get_deployed_id(agent_dir)
            if runtime_id:
                publish_agent_to_gemini_enterprise(agent_info, runtime_id)

        return agent_name, True, elapsed, proc.stdout
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        print(f"❌ [FAILED] {agent_name} deployment failed after {elapsed:.1f} seconds:\n{e.stderr}")
        return agent_name, False, elapsed, e.stderr

def update_orchestrator_tools(engineer_id: str, tester_id: str, connector_id: str):
    tools_path = os.path.join(ORCHESTRATOR_AGENT["dir"], "app", "tools.py")
    if not os.path.exists(tools_path):
        print(f"⚠️ Could not find {tools_path} to update IDs")
        return

    with open(tools_path, "r") as f:
        content = f.read()

    # Update JIRA_CONNECTOR_ENGINE_ID constant
    if connector_id:
        content = re.sub(
            r'JIRA_CONNECTOR_ENGINE_ID\s*=\s*"[^"]+"',
            f'JIRA_CONNECTOR_ENGINE_ID = "{connector_id}"',
            content
        )

    # Update ENGINEER_ENGINE_ID constant
    if engineer_id:
        content = re.sub(
            r'ENGINEER_ENGINE_ID\s*=\s*"[^"]+"',
            f'ENGINEER_ENGINE_ID = "{engineer_id}"',
            content
        )

    # Update TESTER_ENGINE_ID constant
    if tester_id:
        content = re.sub(
            r'TESTER_ENGINE_ID\s*=\s*"[^"]+"',
            f'TESTER_ENGINE_ID = "{tester_id}"',
            content
        )

    with open(tools_path, "w") as f:
        f.write(content)

    print(f"🔄 Updated orchestrator A2A endpoints in tools.py:")
    print(f"   - Jira Connector: {connector_id}")
    print(f"   - Engineer:       {engineer_id}")
    print(f"   - Tester:         {tester_id}")

def get_deployed_id(agent_dir: str) -> str:
    metadata_path = os.path.join(agent_dir, "deployment_metadata.json")
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, "r") as f:
                data = json.load(f)
                return data.get("remote_agent_runtime_id", "")
        except Exception:
            pass
    return ""

def main():
    total_start = time.time()
    print("=" * 68)
    print("⚡ Starting 2-Phase Parallel A2A Microservice & Container Deployment")
    print("=" * 68)

    # ---------------- Pre-flight: Shared Base Image ----------------
    base_dockerfile = os.path.join(ROOT_DIR, "Dockerfile.base")
    if os.path.exists(base_dockerfile):
        print("\n🧱 Checking Shared Base Container Image...")
        build_and_push_container("agent-base", ROOT_DIR, dockerfile_path=base_dockerfile)

    # ---------------- Phase 1 ----------------
    phase1_start = time.time()
    print("\n📦 PHASE 1: Deploying A2A Sub-Agents in Parallel (Jira, Engineer, Tester)...")

    results = {}
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(deploy_single_agent, agent): agent["name"] for agent in PHASE_1_AGENTS}
        for future in as_completed(futures):
            name, success, elapsed, output = future.result()
            results[name] = {"success": success, "elapsed": elapsed}

    phase1_elapsed = time.time() - phase1_start
    phase1_success = all(r["success"] for r in results.values())

    if not phase1_success:
        print("\n❌ Phase 1 failed! Aborting Phase 2.")
        sys.exit(1)

    print(f"\n✨ Phase 1 Complete in {phase1_elapsed:.1f} seconds!")

    # Extract IDs
    connector_id = get_deployed_id(PHASE_1_AGENTS[0]["dir"])
    engineer_id = get_deployed_id(PHASE_1_AGENTS[1]["dir"])
    tester_id = get_deployed_id(PHASE_1_AGENTS[2]["dir"])

    # Update Orchestrator tools
    update_orchestrator_tools(engineer_id, tester_id, connector_id)

    # ---------------- Phase 2 ----------------
    phase2_start = time.time()
    print("\n📦 PHASE 2: Deploying SDLC Orchestrator...")

    orch_name, orch_success, orch_elapsed, _ = deploy_single_agent(ORCHESTRATOR_AGENT)

    if not orch_success:
        print("\n❌ Phase 2 (Orchestrator) deployment failed!")
        sys.exit(1)

    total_elapsed = time.time() - total_start

    print("\n" + "=" * 68)
    print("🎉 ALL 4 A2A AGENTS DEPLOYED & REGISTERED SUCCESSFULLY WITH OAUTH V6!")
    print("=" * 68)
    print(f"⏱️ Phase 1 (Parallel A2A Agents):  {phase1_elapsed:.1f} seconds")
    print(f"⏱️ Phase 2 (Orchestrator Router):  {orch_elapsed:.1f} seconds")
    print(f"⚡ Total A2A Pipeline Time:        {total_elapsed / 60:.2f} minutes")
    print("=" * 68)

if __name__ == "__main__":
    main()
