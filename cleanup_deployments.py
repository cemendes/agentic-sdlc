#!/usr/bin/env python3
import os
import json
import requests
from google.cloud import aiplatform
import vertexai
from vertexai.preview.reasoning_engines import ReasoningEngine
import google.auth
from google.auth.transport.requests import Request

# 1. Initialize Vertex AI
PROJECT_ID = "your-project-id"
PROJECT_NUMBER = "<YOUR_PROJECT_NUMBER>"
LOCATION = "us-central1"
ENGINE_ID = "privia-health-dora_1784047034048"

aiplatform.init(project=PROJECT_ID, location=LOCATION)

ACTIVE_ENGINE_IDS = {
    "projects/<YOUR_PROJECT_NUMBER>/locations/us-central1/reasoningEngines/<REASONING_ENGINE_ID>": "jira-mcp-agent",
    "projects/<YOUR_PROJECT_NUMBER>/locations/us-central1/reasoningEngines/<REASONING_ENGINE_ID>": "sdlc-engineer",
    "projects/<YOUR_PROJECT_NUMBER>/locations/us-central1/reasoningEngines/<REASONING_ENGINE_ID>": "sdlc-tester",
    "projects/<YOUR_PROJECT_NUMBER>/locations/us-central1/reasoningEngines/<REASONING_ENGINE_ID>": "sdlc-orchestrator",
}

print("=" * 65)
print("🧹 Checking & Cleaning Vertex AI Reasoning Engines...")
print("=" * 65)

try:
    from google.cloud.aiplatform_v1beta1 import ReasoningEngineServiceClient
    gapic_client = ReasoningEngineServiceClient(client_options={"api_endpoint": "us-central1-aiplatform.googleapis.com"})

    engines = ReasoningEngine.list()
    print(f"Found {len(engines)} total Reasoning Engine deployment(s) in Vertex AI:")
    for engine in engines:
        res_name = engine.resource_name
        display_name = getattr(engine, "display_name", "N/A")
        if res_name in ACTIVE_ENGINE_IDS:
            print(f"✅ [ACTIVE - KEEP] {ACTIVE_ENGINE_IDS[res_name]} ({res_name})")
        else:
            print(f"🗑️ [STALE - FORCE DELETING] {display_name} ({res_name})...")
            try:
                op = gapic_client.delete_reasoning_engine(request={"name": res_name, "force": True})
                print(f"   Successfully initiated force deletion LRO: {op.operation.name}")
            except Exception as e:
                print(f"   ⚠️ Could not delete {res_name}: {e}")
except Exception as e:
    print(f"⚠️ Error listing/deleting Reasoning Engines: {e}")

print("\n" + "=" * 65)
print("🧹 Checking Gemini Enterprise (Discovery Engine) Registered Agents...")
print("=" * 65)

try:
    creds, _ = google.auth.default()
    if creds.requires_scopes:
        creds = creds.with_scopes(["https://www.googleapis.com/auth/cloud-platform"])
    creds.refresh(Request())

    headers = {
        "Authorization": f"Bearer {creds.token}",
        "Accept": "application/json"
    }
    base_url = f"https://discoveryengine.googleapis.com/v1alpha/projects/{PROJECT_NUMBER}/locations/global/collections/default_collection/engines/{ENGINE_ID}/assistants/default_assistant/agents"

    response = requests.get(base_url, headers=headers)
    if response.status_code == 200:
        data = response.json()
        agents = data.get("agents", [])
        print(f"Found {len(agents)} total agent(s) registered in Gemini Enterprise:")
        for agent in agents:
            name = agent.get("name")
            display_name = agent.get("displayName")
            auth_id = agent.get("authorization")
            print(f"\n   - ID: {name}")
            print(f"     Display Name: {display_name}")
            print(f"     Authorization: {auth_id}")
            print(f"     Full Spec Dump: {json.dumps(agent)}")
            
            is_active = any(active_id in json.dumps(agent) for active_id in ACTIVE_ENGINE_IDS.keys())
            if not is_active:
                print(f"   🗑️ [STALE REGISTRATION - DELETING] {display_name} ({name})...")
                del_res = requests.delete(f"https://discoveryengine.googleapis.com/v1alpha/{name}", headers=headers)
                if del_res.status_code in (200, 204):
                    print(f"      Successfully deleted {name}")
                else:
                    print(f"      ⚠️ Failed to delete {name}: {del_res.status_code} {del_res.text}")
            else:
                print(f"   ✅ [ACTIVE REGISTRATION - KEEP] {display_name}")
    else:
        print(f"⚠️ Could not fetch Gemini Enterprise agents: {response.status_code} {response.text}")
except Exception as e:
    print(f"⚠️ Error cleaning Gemini Enterprise registrations: {e}")

print("\n✨ Cleanup Complete!")
