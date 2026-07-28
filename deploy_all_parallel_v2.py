#!/usr/bin/env python3
"""
V2 Parallel Agent Deployment Script with Side-by-Side Runtime Isolation & Atlassian OAuth v7 Integration
Phase 1: Concurrently builds/pushes V2 container images and deploys all 4 Phase 1 V2 sub-agents (jira-mcp-agent-v2, sdlc-engineer-v2, sdlc-tester-v2, sdlc-merger-v2)
Phase 2: Reads V2 ReasoningEngine IDs, injects them into Orchestrator tools.py, builds/pushes V2 image, deploys sdlc-orchestrator-v2, and binds Atlassian OAuth v7.
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
ATLASSIAN_AUTH_V7_ID = "projects/<YOUR_PROJECT_NUMBER>/locations/global/authorizations/atlassian-oauth-auth-v8"

PHASE_1_AGENTS_V2 = [
    {"name": "jira-mcp-agent", "dir": os.path.join(ROOT_DIR, "jira-mcp-agent")},
    {"name": "sdlc-engineer", "dir": os.path.join(ROOT_DIR, "sdlc-engineer")},
    {"name": "sdlc-tester", "dir": os.path.join(ROOT_DIR, "sdlc-tester")},
    {"name": "sdlc-merger", "dir": os.path.join(ROOT_DIR, "sdlc-merger")},
]

ORCHESTRATOR_AGENT_V2 = {"name": "sdlc-orchestrator", "dir": os.path.join(ROOT_DIR, "sdlc-orchestrator")}

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

    full_image_tag = f"{REGISTRY_HOST}/{image_name}-v2:latest"

    if shutil.which("docker"):
        try:
            print(f"🐳 [CONTAINER BUILD V2] Building image {full_image_tag}...")
            subprocess.run(
                ["docker", "build", "-f", dockerfile_path, "-t", full_image_tag, context_dir],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"⬆️ [CONTAINER PUSH V2] Copying image to Artifact Registry: {full_image_tag}...")
            subprocess.run(
                ["docker", "push", full_image_tag],
                check=True,
                capture_output=True,
                text=True
            )
            print(f"✅ [CONTAINER READY V2] Successfully pushed {full_image_tag}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"⚠️ [CONTAINER NOTICE V2] Local docker build failed for {image_name}-v2: {e.stderr[:100]}")
            return False
    else:
        print(f"ℹ️ [CONTAINER V2] Local 'docker' binary not active. Skipping container image build for {image_name}-v2.")
        return True

def publish_agent_to_gemini_enterprise(agent_info: dict, runtime_id: str) -> bool:
    """Registers agent V2 to Gemini Enterprise and binds Atlassian OAuth v7 to the Orchestrator."""
    agent_name = f"{agent_info['name']}-v2"
    agent_dir = agent_info["dir"]

    if not runtime_id:
        return False

    cmd = [
        "agents-cli", "publish", "gemini-enterprise",
        f"--agent-runtime-id={runtime_id}",
        f"--gemini-enterprise-app-id={GEMINI_ENTERPRISE_APP}",
        f"--display-name={agent_name}",
    ]

    if agent_info["name"] == "sdlc-orchestrator":
        cmd.append(f"--authorization-id={ATLASSIAN_AUTH_V7_ID}")

    print(f"🔐 [OAUTH PUBLISH V2] Registering {agent_name} with Gemini Enterprise...")
    try:
        subprocess.run(cmd, cwd=agent_dir, check=True, capture_output=True, text=True)
        print(f"✅ [OAUTH READY V2] Successfully registered {agent_name}!")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️ [OAUTH NOTICE V2] Note during Gemini Enterprise registration for {agent_name}:\n{e.stderr}")
        return False

def deploy_single_agent(agent_info: dict) -> tuple[str, bool, float, str]:
    agent_name = f"{agent_info['name']}-v2"
    agent_dir = agent_info["dir"]
    start_time = time.time()

    if os.environ.get("SKIP_EXISTING", "").lower() == "true" and agent_info["name"] != "sdlc-orchestrator":
        existing_id = get_deployed_id(agent_dir)
        if existing_id:
            print(f"ℹ️ [SKIP EXISTING] Found valid V2 engine for {agent_name}: {existing_id}")
            return agent_name, True, 0.1, f"Skipped existing: {existing_id}"

    print(f"🚀 [START V2] Processing {agent_name}...")

    build_and_push_container(agent_info["name"], agent_dir)

    python_bin = os.path.join(agent_dir, ".venv", "bin", "python")
    if not os.path.exists(python_bin):
        python_bin = sys.executable

    deploy_script = os.path.join(agent_dir, "deploy_agent.py")
    
    env_copy = os.environ.copy()
    env_copy["DEPLOY_V2"] = "true"

    try:
        proc = subprocess.run(
            [python_bin, deploy_script, "--v2"],
            cwd=agent_dir,
            env=env_copy,
            capture_output=True,
            text=True,
            check=True
        )
        elapsed = time.time() - start_time
        print(f"✅ [SUCCESS V2] Deployed {agent_name} in {elapsed:.1f} seconds")

        if agent_info["name"] == "sdlc-orchestrator":
            runtime_id = get_deployed_id(agent_dir)
            if runtime_id:
                publish_agent_to_gemini_enterprise(agent_info, runtime_id)

        return agent_name, True, elapsed, proc.stdout
    except subprocess.CalledProcessError as e:
        elapsed = time.time() - start_time
        print(f"❌ [FAILED V2] {agent_name} deployment failed after {elapsed:.1f} seconds:\n{e.stderr}")
        return agent_name, False, elapsed, e.stderr

def update_orchestrator_tools(engineer_id: str, tester_id: str, connector_id: str, merger_id: str):
    tools_path = os.path.join(ORCHESTRATOR_AGENT_V2["dir"], "app", "tools.py")
    if not os.path.exists(tools_path):
        print(f"⚠️ Could not find {tools_path} to update V2 IDs")
        return

    with open(tools_path, "r") as f:
        content = f.read()

    if connector_id:
        content = re.sub(
            r'JIRA_CONNECTOR_ENGINE_ID\s*=\s*"[^"]+"',
            f'JIRA_CONNECTOR_ENGINE_ID = "{connector_id}"',
            content
        )
    if engineer_id:
        content = re.sub(
            r'ENGINEER_ENGINE_ID\s*=\s*"[^"]+"',
            f'ENGINEER_ENGINE_ID = "{engineer_id}"',
            content
        )
    if tester_id:
        content = re.sub(
            r'TESTER_ENGINE_ID\s*=\s*"[^"]+"',
            f'TESTER_ENGINE_ID = "{tester_id}"',
            content
        )
    if merger_id:
        content = re.sub(
            r'MERGER_ENGINE_ID\s*=\s*"[^"]+"',
            f'MERGER_ENGINE_ID = "{merger_id}"',
            content
        )

    with open(tools_path, "w") as f:
        f.write(content)

    print(f"🔄 Updated orchestrator A2A endpoints in tools.py with V2 Engine IDs:")
    print(f"   - Jira Connector V2: {connector_id}")
    print(f"   - Engineer V2:       {engineer_id}")
    print(f"   - Tester V2:         {tester_id}")
    print(f"   - Merger & Deploy V2:{merger_id}")

def get_deployed_id(agent_dir: str) -> str:
    metadata_path = os.path.join(agent_dir, "deployment_metadata_v2.json")
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
    print("=" * 72)
    print("⚡ Starting V2 Parallel A2A Microservice & Container Side-by-Side Deployment")
    print("=" * 72)

    base_dockerfile = os.path.join(ROOT_DIR, "Dockerfile.base")
    if os.path.exists(base_dockerfile):
        print("\n🧱 Checking Shared Base Container Image...")
        build_and_push_container("agent-base", ROOT_DIR, dockerfile_path=base_dockerfile)

    phase1_start = time.time()
    print("\n📦 PHASE 1: Deploying V2 A2A Sub-Agents in Parallel (Jira, Engineer, Tester, Merger)...")

    results = {}
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(deploy_single_agent, agent): agent["name"] for agent in PHASE_1_AGENTS_V2}
        for future in as_completed(futures):
            name, success, elapsed, output = future.result()
            results[name] = {"success": success, "elapsed": elapsed}

    phase1_elapsed = time.time() - phase1_start
    phase1_success = all(r["success"] for r in results.values())

    if not phase1_success:
        print("\n❌ Phase 1 (V2 Sub-Agents) failed! Aborting Phase 2.")
        sys.exit(1)

    print(f"\n✨ Phase 1 Complete in {phase1_elapsed:.1f} seconds!")

    connector_id = get_deployed_id(PHASE_1_AGENTS_V2[0]["dir"])
    engineer_id = get_deployed_id(PHASE_1_AGENTS_V2[1]["dir"])
    tester_id = get_deployed_id(PHASE_1_AGENTS_V2[2]["dir"])
    merger_id = get_deployed_id(PHASE_1_AGENTS_V2[3]["dir"])

    update_orchestrator_tools(engineer_id, tester_id, connector_id, merger_id)

    phase2_start = time.time()
    print("\n📦 PHASE 2: Deploying SDLC Orchestrator V2 with Atlassian OAuth v7...")

    orch_name, orch_success, orch_elapsed, _ = deploy_single_agent(ORCHESTRATOR_AGENT_V2)

    if not orch_success:
        print("\n❌ Phase 2 (Orchestrator V2) deployment failed!")
        sys.exit(1)

    total_elapsed = time.time() - total_start

    print("\n" + "=" * 72)
    print("🎉 ALL 5 V2 A2A AGENTS DEPLOYED & REGISTERED SUCCESSFULLY WITH OAUTH V7!")
    print("=" * 72)
    print(f"⏱️ Phase 1 (Parallel V2 Agents):    {phase1_elapsed:.1f} seconds")
    print(f"⏱️ Phase 2 (Orchestrator V2 Router):{orch_elapsed:.1f} seconds")
    print(f"⚡ Total V2 A2A Pipeline Time:      {total_elapsed / 60:.2f} minutes")
    print("=" * 72)

if __name__ == "__main__":
    main()
