#!/usr/bin/env python3
"""
Local Fast-Runner & Test Harness for 5-Agent A2A SDLC Workflow.
Runs the entire Orchestrator -> Jira -> Engineer -> Tester -> Merger pipeline
locally in memory on your Mac in < 5 seconds per turn!
"""
import os
import sys
import asyncio
import argparse

# Ensure project root is in sys.path
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Set environment for Vertex AI & Local Dev
os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "True"
os.environ["GOOGLE_CLOUD_LOCATION"] = "global"
os.environ["LOCAL_DEV"] = "true"

from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

def load_local_sub_agent(folder_name: str):
    """Loads an ADK sub-agent module locally in memory."""
    full_path = os.path.join(BASE_DIR, folder_name)
    if full_path not in sys.path:
        sys.path.insert(0, full_path)
        
    # Clear cached 'app' modules to avoid collisions across sub-agents
    for mod in list(sys.modules.keys()):
        if mod == "app" or mod.startswith("app."):
            del sys.modules[mod]
            
    import app.agent
    return app.agent.root_agent

async def run_local_pipeline(ticket_key: str, custom_prompt: str = None):
    print("=" * 80)
    print(f"🚀 LOCAL FAST-RUNNER: Executing SDLC Pipeline for {ticket_key}")
    print("=" * 80)
    
    prompt = custom_prompt or f"Run the bug-fix pipeline for {ticket_key}"
    
    print("\n📦 Loading local Orchestrator agent...")
    orchestrator_agent = load_local_sub_agent("sdlc-orchestrator")
    
    session_service = InMemorySessionService()
    runner = Runner(agent=orchestrator_agent, app_name=orchestrator_agent.name, session_service=session_service)
    session = await session_service.create_session(user_id="local_tester", app_name=orchestrator_agent.name)
    session_id = getattr(session, "id", getattr(session, "session_id", None))
    
    print(f"⚡ Session ID: {session_id}")
    print(f"💬 Prompt: '{prompt}'\n")
    print("-" * 80)
    
    msg = types.Content(role="user", parts=[types.Part.from_text(text=prompt)])
    
    step_count = 0
    async for ev in runner.run_async(user_id="local_tester", session_id=session_id, new_message=msg):
        if hasattr(ev, "content") and ev.content:
            for part in ev.content.parts:
                if hasattr(part, "function_call") and part.function_call:
                    step_count += 1
                    fc = part.function_call
                    print(f"\n🔧 [STEP {step_count} TOOL CALL]: {fc.name}", flush=True)
                    print(f"   Args: {fc.args}", flush=True)
                    
                if hasattr(part, "function_response") and part.function_response:
                    fr = part.function_response
                    res_str = str(fr.response)
                    if len(res_str) > 200:
                        res_str = res_str[:200] + f"... [truncated {len(res_str)} chars]"
                    print(f"   📥 Output: {res_str}", flush=True)
                    
                if hasattr(part, "text") and part.text and part.text.strip():
                    print(f"\n🤖 [AGENT RESPONSE]:\n{part.text.strip()}", flush=True)

    print("\n" + "=" * 80, flush=True)
    print(f"✅ LOCAL PIPELINE TEST COMPLETE FOR {ticket_key}!", flush=True)
    print("=" * 80, flush=True)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run local SDLC Multi-Agent Pipeline")
    parser.add_argument("--ticket", type=str, default="SCRUM-11", help="Jira Ticket Key (e.g. SCRUM-11)")
    parser.add_argument("--prompt", type=str, default=None, help="Custom prompt string")
    args = parser.parse_args()
    
    asyncio.run(run_local_pipeline(args.ticket, args.prompt))
