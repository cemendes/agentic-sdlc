import os
import sys
import json
import shutil

sys.path.insert(0, os.path.abspath("."))
for mod in list(sys.modules.keys()):
    if mod == "app" or mod.startswith("app."):
        del sys.modules[mod]

from google.cloud import aiplatform
import vertexai
from vertexai.preview.reasoning_engines import ReasoningEngine
from app.agent_runtime_app import agent_runtime

# Initialize Vertex AI
aiplatform.init(
    project="your-project-id",
    location="us-central1",
    staging_bucket="gs://your-project-id-agent-engine-staging",
)

# Read requirements
with open("requirements.txt", "r") as f:
    requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]

is_v2 = "--v2" in sys.argv or os.environ.get("DEPLOY_V2", "").lower() == "true"
meta_file = "deployment_metadata_v2.json" if is_v2 else "deployment_metadata.json"
display_name = "sdlc-merger-v2" if is_v2 else "sdlc-merger"

# Check if metadata file already has an existing runtime ID to update in-place
existing_id = None
if os.path.exists(meta_file):
    try:
        with open(meta_file, "r") as f:
            meta = json.load(f)
            existing_id = meta.get("remote_agent_runtime_id")
    except Exception:
        pass

env_exists = os.path.exists(".env")
if env_exists:
    shutil.move(".env", ".env.tmp")

try:
    if existing_id:
        print(f"🔄 Updating existing Agent Runtime in-place ({meta_file}): {existing_id}...")
        remote_app = ReasoningEngine(existing_id)
        remote_app.update(
            reasoning_engine=agent_runtime,
            requirements=requirements,
            display_name=display_name,
            extra_packages=["app"],
        )
    else:
        print(f"🚀 Deploying initial Agent Runtime ({display_name})...")
        remote_app = ReasoningEngine.create(
            reasoning_engine=agent_runtime,
            requirements=requirements,
            display_name=display_name,
            extra_packages=["app"],
        )
finally:
    if env_exists:
        shutil.move(".env.tmp", ".env")

print(f"Successfully processed! Resource Name: {remote_app.resource_name}")

# Update metadata file
with open(meta_file, "w") as f:
    json.dump({
        "remote_agent_runtime_id": remote_app.resource_name,
        "deployment_target": "agent_runtime",
        "is_a2a": True,
    }, f, indent=2)
