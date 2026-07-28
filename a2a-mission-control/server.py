#!/usr/bin/env python3
"""
A2A Mission Control Real-Time Telemetry & Event Broker Server
A lightweight, zero-dependency Python asynchronous HTTP & Server-Sent Events (SSE) server.
Serves static frontend files, ingests telemetry from SDLC Orchestrator A2A loops, and broadcasts live events.
"""

import http.server
import socketserver
import threading
import json
import time
import os
import sys
import urllib.parse
from datetime import datetime
import sqlite3

PORT = int(os.environ.get("A2A_DASHBOARD_PORT", "5050"))
WEB_DIR = os.path.abspath(os.path.dirname(__file__))

# Global Thread-Safe Client Connection Management for SSE
sse_clients = set()
sse_lock = threading.Lock()

# In-Memory Event Log & Persistent SQLite Setup
DB_PATH = os.path.join(WEB_DIR, "telemetry_history.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trace_id TEXT,
            source TEXT,
            target TEXT,
            action TEXT,
            status TEXT,
            payload TEXT,
            metadata TEXT,
            timestamp TEXT
        )
    ''')
    conn.commit()
    conn.close()

def store_event(event):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO events (trace_id, source, target, action, status, payload, metadata, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        event.get("trace_id", "GENERAL"),
        event.get("source", "System"),
        event.get("target", "System"),
        event.get("action", "EVENT"),
        event.get("status", "INFO"),
        isinstance(event.get("payload"), dict) and json.dumps(event.get("payload")) or str(event.get("payload", "")),
        json.dumps(event.get("metadata", {})),
        event.get("timestamp", datetime.now().isoformat())
    ))
    conn.commit()
    conn.close()

def get_recent_events(limit=100):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT trace_id, source, target, action, status, payload, metadata, timestamp FROM events ORDER BY id DESC LIMIT ?', (limit,))
    rows = c.fetchall()
    conn.close()
    events = []
    for r in rows:
        try:
            meta = json.loads(r[6]) if r[6] else {}
        except Exception:
            meta = {}
        events.append({
            "trace_id": r[0],
            "source": r[1],
            "target": r[2],
            "action": r[3],
            "status": r[4],
            "payload": r[5],
            "metadata": meta,
            "timestamp": r[7]
        })
    return list(reversed(events))

def broadcast_event(event):
    store_event(event)
    data_str = f"data: {json.dumps(event)}\n\n".encode('utf-8')
    with sse_lock:
        dead_clients = set()
        for client in sse_clients:
            try:
                client.wfile.write(data_str)
                client.wfile.flush()
            except Exception:
                dead_clients.add(client)
        for dead in dead_clients:
            sse_clients.discard(dead)

# Simulate realistic Jira SDLC A2A Multi-Agent loop for test/demo purposes
def run_simulation_loop(trace_id, ticket_key, bug_desc):
    def emit(source, target, action, status, payload, metadata=None):
        event = {
            "trace_id": trace_id,
            "source": source,
            "target": target,
            "action": action,
            "status": status,
            "payload": payload,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat()
        }
        broadcast_event(event)
        time.sleep(1.8)

    # Step 1: Orchestrator initialized
    emit("SDLC Orchestrator", "Jira MCP Connector", "A2A_HANDOFF_INITIATED", "ACTIVE", f"Querying issue details & status for {ticket_key}...", {"token_count": 84, "duration_ms": 120})
    
    # Step 2: Jira Connector responds & OAuth status checked
    emit("Jira MCP Connector", "SDLC Orchestrator", "A2A_HANDOFF_COMPLETED", "SUCCESS", f"Issue found: {ticket_key} - '{bug_desc}'. Status transitioned to 'In Progress'. Atlassian OAuth V6 Authorized.", {"oauth_status": "Authorized (V6)", "token_count": 340, "duration_ms": 1420})
    
    # Step 3: Orchestrator delegates to Engineer
    emit("SDLC Orchestrator", "Engineer Agent", "A2A_HANDOFF_INITIATED", "ACTIVE", f"Delegating fix instruction for {ticket_key}: {bug_desc}", {"token_count": 190, "duration_ms": 95})
    
    # Step 4: Engineer analyzes and writes fix patch
    git_diff_payload = f"""diff --git a/src/app.py b/src/app.py
index 8f3b2a..a1c4e9 100644
--- a/src/app.py
+++ b/src/app.py
@@ -45,7 +45,7 @@ def process_user_request(request):
-    logger.warn("Processing user transaction without validation")
-    return execute_direct(request.payload)
+    logger.info("Validating user request payload against schema")
+    if not validate_schema(request.payload):
+        raise ValueError("Invalid request structure in {ticket_key}")
+    return execute_secure(request.payload)
"""
    emit("Engineer Agent", "SDLC Orchestrator", "DIFF_PRODUCED", "SUCCESS", f"BRANCH: fix/{ticket_key.lower()}-validation-fix\nCommitted and pushed clean patch to Google Secure Source Manager.", {"git_branch": f"fix/{ticket_key.lower()}-validation-fix", "diff": git_diff_payload, "token_count": 920, "duration_ms": 4200})
    
    # Step 5: Orchestrator delegates verification to Tester
    emit("SDLC Orchestrator", "Tester Agent", "A2A_HANDOFF_INITIATED", "ACTIVE", f"Verify test suite on branch fix/{ticket_key.lower()}-validation-fix", {"token_count": 150, "duration_ms": 110})
    
    # Step 6: Tester runs pytest verification
    test_stdout = f"""============================= test session starts ==============================
platform darwin -- Python 3.11.8, pytest-8.1.1, pluggy-1.4.0
rootdir: /workspace/sdlc-test-repo
collected 14 items

tests/test_app.py::test_user_request_validation PASSED                   [ 28%]
tests/test_app.py::test_schema_rejection PASSED                          [ 57%]
tests/test_app.py::test_execute_secure_pipeline PASSED                   [ 85%]
tests/test_integration.py::test_full_lifecycle PASSED                    [100%]

============================== 14 passed in 1.42s =============================="""
    emit("Tester Agent", "SDLC Orchestrator", "TEST_EXECUTION_RESULT", "SUCCESS", "All automated verification tests passed successfully.", {"test_stdout": test_stdout, "tests_passed": 14, "tests_failed": 0, "token_count": 510, "duration_ms": 3100})
    
    # Step 7: Orchestrator finalizes ticket in Jira
    emit("SDLC Orchestrator", "Jira MCP Connector", "A2A_HANDOFF_INITIATED", "ACTIVE", f"Posting verification comment and transitioning {ticket_key} to Done.", {"token_count": 120, "duration_ms": 130})
    emit("Jira MCP Connector", "SDLC Orchestrator", "A2A_HANDOFF_COMPLETED", "SUCCESS", f"Ticket {ticket_key} marked as Done with automated verification logs attached.", {"oauth_status": "Authorized (V6)", "token_count": 210, "duration_ms": 980})
    emit("SDLC Orchestrator", "System", "TASK_COMPLETED", "GREEN", f"Bug-fix workflow complete for {ticket_key}. Verification confirmed.", {"token_count": 50, "duration_ms": 40})

class MissionControlHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        if path == "/api/stream":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            
            with sse_lock:
                sse_clients.add(self)
            
            # Send initial greeting event and recent history
            init_event = {
                "trace_id": "SYSTEM",
                "source": "A2A Server",
                "target": "Dashboard Client",
                "action": "STREAM_CONNECTED",
                "status": "GREEN",
                "payload": "Real-time SSE event telemetry stream active.",
                "timestamp": datetime.now().isoformat()
            }
            try:
                self.wfile.write(f"data: {json.dumps(init_event)}\n\n".encode('utf-8'))
                self.wfile.flush()
            except Exception:
                return
                
            # Block thread to maintain SSE connection alive
            while True:
                try:
                    time.sleep(15)
                    self.wfile.write(": keepalive\n\n".encode('utf-8'))
                    self.wfile.flush()
                except Exception:
                    with sse_lock:
                        sse_clients.discard(self)
                    break
            return

        elif path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            events = get_recent_events(100)
            self.wfile.write(json.dumps({"status": "success", "events": events}).encode('utf-8'))
            return

        elif path == "/api/clear":
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("DELETE FROM events")
            conn.commit()
            conn.close()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "cleared"}).encode('utf-8'))
            return

        # Serve static files normally
        super().do_GET()

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        content_len = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_len).decode('utf-8') if content_len > 0 else "{}"
        try:
            payload_json = json.loads(body)
        except Exception:
            payload_json = {}

        if path == "/api/emit":
            event = {
                "trace_id": payload_json.get("trace_id", "A2A-TRACE"),
                "source": payload_json.get("source", "Unknown Agent"),
                "target": payload_json.get("target", "System"),
                "action": payload_json.get("action", "LOG_EVENT"),
                "status": payload_json.get("status", "ACTIVE"),
                "payload": payload_json.get("payload", ""),
                "metadata": payload_json.get("metadata", {}),
                "timestamp": datetime.now().isoformat()
            }
            threading.Thread(target=broadcast_event, args=(event,), daemon=True).start()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok", "message": "Event broadcasted"}).encode('utf-8'))
            return

        elif path == "/api/sandbox" or path == "/api/chat":
            ticket_key = payload_json.get("ticket_key", "SCRUM-11")
            prompt_text = payload_json.get("prompt", payload_json.get("bug_description", ""))
            trace_id = f"RUN-{int(time.time())}"
            threading.Thread(target=run_real_pipeline_thread, args=(trace_id, ticket_key, prompt_text), daemon=True).start()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "started", "trace_id": trace_id}).encode('utf-8'))
            return

        self.send_response(404)
        self.end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

class ThreadedHTTPServer(socketserver.ThreadingMixIn, http.server.HTTPServer):
    daemon_threads = True

def main():
    init_db()
    server_address = ('', PORT)
    httpd = ThreadedHTTPServer(server_address, MissionControlHandler)
    print(f"🚀 [A2A MISSION CONTROL] Server started on http://localhost:{PORT}")
    print(f"📡 [SSE STREAM] Listening for live events on http://localhost:{PORT}/api/emit")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
        httpd.server_close()

if __name__ == "__main__":
    main()
