# Copyright 2026 Google LLC
"""
A2A Mission Control Telemetry Intercept Client
Provides non-blocking, fail-safe event emitting to the local or remote A2A Mission Control Dashboard server.
"""

import os
import json
import threading
import urllib.request
import urllib.error
from datetime import datetime
from typing import Optional, Dict, Any

TELEMETRY_URL = os.environ.get("A2A_MISSION_CONTROL_URL", "http://localhost:5050/api/emit")

def _send_event_thread(payload: Dict[str, Any]):
    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            TELEMETRY_URL,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            pass
    except (urllib.error.URLError, TimeoutError, Exception):
        # Gracefully ignore connection failures if Control Panel server is offline
        pass

def emit_telemetry(
    source: str,
    target: str,
    action: str,
    status: str,
    payload: str,
    metadata: Optional[Dict[str, Any]] = None,
    trace_id: Optional[str] = None
):
    """Asynchronously emit an A2A execution milestone without blocking reasoning engine execution."""
    event_payload = {
        "trace_id": trace_id or os.environ.get("A2A_TRACE_ID", "A2A-LIVE"),
        "source": source,
        "target": target,
        "action": action,
        "status": status,
        "payload": payload,
        "metadata": metadata or {},
        "timestamp": datetime.now().isoformat()
    }
    threading.Thread(target=_send_event_thread, args=(event_payload,), daemon=True).start()

def setup_telemetry() -> Optional[str]:
    """Initialize telemetry services (no-op / placeholder for compatibility with agent_runtime_app)."""
    return None
