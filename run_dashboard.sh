#!/bin/bash
# Copyright 2026 Google LLC
# Launches the A2A Mission Control Panel Real-Time Dashboard

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" &> /dev/null && pwd)"
SERVER_SCRIPT="$SCRIPT_DIR/a2a-mission-control/server.py"

echo "===================================================================="
echo "⚡ LAUNCHING A2A MISSION CONTROL REAL-TIME TELEMETRY DASHBOARD"
echo "===================================================================="
echo "🌐 Dashboard Web UI:      http://localhost:5050"
echo "📡 Telemetry Event Sink:  http://localhost:5050/api/emit"
echo "===================================================================="

# Run zero-dependency server
python3 "$SERVER_SCRIPT"
