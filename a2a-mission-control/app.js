// A2A Mission Control Frontend Application Logic
let activeTab = 'topology';
let totalTokens = 0;
let defaultInspectData = {
    branch: 'fix/scrum-42-validation',
    diff: `diff --git a/src/app.py b/src/app.py
index 8f3b2a..a1c4e9 100644
--- a/src/app.py
+++ b/src/app.py
@@ -45,7 +45,7 @@ def process_user_request(request):
-    logger.warn("Processing user transaction without validation")
-    return execute_direct(request.payload)
+    logger.info("Validating user request payload against schema")
+    if not validate_schema(request.payload):
+        raise ValueError("Invalid request structure in SCRUM-42")
+    return execute_secure(request.payload)`,
    term: `(venv) root@sdlc-tester:~# pytest tests/test_app.py --verbose
============================= test session starts ==============================
platform darwin -- Python 3.11.8, pytest-8.1.1
collecting ... 14 items collected

tests/test_app.py::test_user_request_validation PASSED [ 28%]
tests/test_app.py::test_schema_rejection PASSED [ 57%]
tests/test_app.py::test_execute_secure_pipeline PASSED [ 85%]
tests/test_integration.py::test_full_lifecycle PASSED [100%]

============================== 14 passed in 1.42s ==============================
status: Success (Verified clean git patch)`
};

// Initialize application on DOM content load
document.addEventListener("DOMContentLoaded", () => {
    initSSEStream();
    drawConnectingLines();
    window.addEventListener("resize", drawConnectingLines);
});

// Navigation Tab Switcher
function switchTab(tabId) {
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    const tabEl = document.getElementById(`tab-${tabId}`);
    if (tabEl) tabEl.classList.add('active');
    
    // Highlight button
    const btns = document.querySelectorAll('.tab-btn');
    if (tabId === 'topology') btns[0].classList.add('active');
    if (tabId === 'inspector') btns[1].classList.add('active');
    if (tabId === 'sandbox') btns[2].classList.add('active');
    
    if (tabId === 'topology') {
        setTimeout(drawConnectingLines, 50);
    }
}

// Server-Sent Events (SSE) Live Stream Integration
function initSSEStream() {
    const streamUrl = "/api/stream";
    const eventSource = new EventSource(streamUrl);
    
    eventSource.onopen = () => {
        document.getElementById("connection-status").textContent = "● Live Stream Active";
        document.getElementById("connection-status").style.color = "var(--emerald-glow)";
    };
    
    eventSource.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            handleLiveEvent(data);
        } catch (e) {
            console.error("Error parsing telemetry payload:", e);
        }
    };
    
    eventSource.onerror = (err) => {
        document.getElementById("connection-status").textContent = "○ Stream Disconnected";
        document.getElementById("connection-status").style.color = "var(--text-secondary)";
    };
}

// Handle real-time incoming events from backend broker
function handleLiveEvent(evt) {
    appendLog(evt);
    
    // Update global header metrics if available
    if (evt.metadata) {
        if (evt.metadata.token_count) {
            totalTokens += evt.metadata.token_count;
            document.getElementById("token-counter").textContent = totalTokens.toLocaleString();
        }
        if (evt.metadata.oauth_status) {
            document.getElementById("oauth-status").textContent = `✓ ${evt.metadata.oauth_status}`;
        }
        if (evt.metadata.git_branch || evt.metadata.diff || evt.metadata.test_stdout) {
            addInspectorCard(evt);
        }
    }

    // Animate Topology Nodes based on Source and Target
    animateHandoff(evt.source, evt.target, evt.action, evt.status);
}

// Append entry to bottom streaming log
function appendLog(evt) {
    const logBox = document.getElementById("stream-log");
    const entry = document.createElement("div");
    entry.className = "log-entry";
    
    let badgeClass = "badge-init";
    if (evt.action.includes("COMPLETED")) badgeClass = "badge-comp";
    if (evt.action.includes("DIFF")) badgeClass = "badge-diff";
    if (evt.action.includes("TEST")) badgeClass = "badge-test";
    
    const timeStr = evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : "Now";
    entry.innerHTML = `
        <span class="log-time">${timeStr}</span>
        <span class="log-badge ${badgeClass}">${evt.action || 'EVENT'}</span>
        <span class="log-source">${evt.source || 'Agent'}</span>
        <span class="log-arrow">→</span>
        <span class="log-msg">${evt.payload || ''}</span>
    `;
    logBox.appendChild(entry);
    logBox.scrollTop = logBox.scrollHeight;
}

// Animate Nodes and svg connectors during live routing
function animateHandoff(source, target, action, status) {
    // Reset classes
    ["orch", "jira", "eng", "test"].forEach(id => {
        const el = document.getElementById(`node-${id}`);
        if (el) el.classList.remove("active-routing", "success-status");
    });
    document.querySelectorAll(".connector-line").forEach(line => line.classList.remove("active"));
    
    let targetNodeId = null;
    let targetLineId = null;
    let statusId = null;
    
    if (target.includes("Jira") || source.includes("Jira")) {
        targetNodeId = "node-jira"; targetLineId = "line-jira"; statusId = "status-jira";
    } else if (target.includes("Engineer") || source.includes("Engineer")) {
        targetNodeId = "node-eng"; targetLineId = "line-eng"; statusId = "status-eng";
    } else if (target.includes("Tester") || source.includes("Tester")) {
        targetNodeId = "node-test"; targetLineId = "line-test"; statusId = "status-test";
    } else if (target.includes("Merger") || target.includes("Deployer") || source.includes("Merger")) {
        targetNodeId = "node-merger"; targetLineId = "line-merger"; statusId = "status-merger";
    }
    
    const orchNode = document.getElementById("node-orch");
    if (orchNode) orchNode.classList.add("active-routing");
    
    if (targetNodeId) {
        const node = document.getElementById(targetNodeId);
        if (node) {
            node.classList.add(status === "SUCCESS" || status === "GREEN" ? "success-status" : "active-routing");
        }
        if (statusId) {
            document.getElementById(statusId).textContent = status === "SUCCESS" ? "Verified" : "Processing...";
        }
    }
    if (targetLineId) {
        const line = document.getElementById(targetLineId);
        if (line) line.classList.add("active");
    }
    
    // Clear animation state after 3 seconds
    setTimeout(() => {
        if (targetNodeId && document.getElementById(targetNodeId)) {
            document.getElementById(targetNodeId).classList.remove("active-routing");
            if (statusId) document.getElementById(statusId).textContent = "Ready";
        }
        if (targetLineId && document.getElementById(targetLineId)) {
            document.getElementById(targetLineId).classList.remove("active");
        }
        if (orchNode) orchNode.classList.remove("active-routing");
    }, 3500);
}

// Draw dynamic SVG curves between Orchestrator and domain agents
function drawConnectingLines() {
    const svg = document.getElementById("topology-svg");
    if (!svg) return;
    svg.innerHTML = "";
    
    const stageRect = document.querySelector(".node-stage").getBoundingClientRect();
    const orchEl = document.getElementById("node-orch");
    if (!orchEl) return;
    
    const orchRect = orchEl.getBoundingClientRect();
    const startX = orchRect.right - stageRect.left;
    const startY = orchRect.top - stageRect.top + (orchRect.height / 2);
    
    const targets = [
        { el: document.getElementById("node-jira"), id: "line-jira" },
        { el: document.getElementById("node-eng"), id: "line-eng" },
        { el: document.getElementById("node-test"), id: "line-test" },
        { el: document.getElementById("node-merger"), id: "line-merger" }
    ];
    
    targets.forEach(target => {
        if (!target.el) return;
        const rect = target.el.getBoundingClientRect();
        const endX = rect.left - stageRect.left;
        const endY = rect.top - stageRect.top + (rect.height / 2);
        
        // Cubic bezier control points for smooth tech curve
        const cp1x = startX + (endX - startX) / 2;
        const cp1y = startY;
        const cp2x = startX + (endX - startX) / 2;
        const cp2y = endY;
        
        const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
        path.setAttribute("d", `M ${startX} ${startY} C ${cp1x} ${cp1y}, ${cp2x} ${cp2y}, ${endX} ${endY}`);
        path.setAttribute("class", "connector-line");
        path.setAttribute("id", target.id);
        svg.appendChild(path);
    });
}

// Add card to Inspector timeline
function addInspectorCard(evt) {
    const list = document.getElementById("timeline-list");
    const card = document.createElement("div");
    card.className = "timeline-card";
    const timeStr = new Date().toLocaleTimeString();
    
    const branchName = evt.metadata.git_branch || "fix/dynamic-update";
    const diffText = evt.metadata.diff || defaultInspectData.diff;
    const termText = evt.metadata.test_stdout || defaultInspectData.term;
    
    card.innerHTML = `
        <div class="card-top">
            <span>${timeStr}</span>
            <span style="color: var(--cyan-glow); font-weight: 700;">ACTIVE LOOP</span>
        </div>
        <div class="card-title"><span>🔄</span> ${evt.source} → ${evt.target}</div>
        <div class="card-summary">${evt.payload.slice(0, 100)}...</div>
    `;
    
    card.onclick = () => {
        document.querySelectorAll(".timeline-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
        updateInspectorPanel({ branch: branchName, diff: diffText, term: termText });
    };
    
    list.prepend(card);
    card.click();
}

function selectCard(element, data) {
    document.querySelectorAll(".timeline-card").forEach(c => c.classList.remove("selected"));
    element.classList.add("selected");
    updateInspectorPanel(data);
}

// Update Right Column Details in Inspector View
function updateInspectorPanel(data) {
    document.getElementById("inspect-branch").textContent = `Branch: ${data.branch || 'main'}`;
    
    // Format diff text with HTML highlights
    const diffEl = document.getElementById("inspect-diff-viewer");
    const lines = (data.diff || "").split("\n");
    const formatted = lines.map(line => {
        if (line.startsWith("+++") || line.startsWith("---") || line.startsWith("diff") || line.startsWith("index")) {
            return `<span class="diff-hdr">${line}</span>`;
        } else if (line.startsWith("+")) {
            return `<span class="diff-add">${line}</span>`;
        } else if (line.startsWith("-")) {
            return `<span class="diff-sub">${line}</span>`;
        }
        return line;
    }).join("\n");
    diffEl.innerHTML = formatted;

    // Format Terminal stdout
    const termEl = document.getElementById("inspect-term-viewer");
    let termText = data.term || "";
    termText = termText.replace(/(PASSED|14 passed|Success)/g, '<span class="term-pass">$1</span>');
    termEl.innerHTML = termText;
}

// Trigger Interactive Simulation Harness
function triggerTestSimulation() {
    fetch("/api/sandbox", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            ticket_key: "SCRUM-42",
            bug_description: "Null pointer exception occurred in user authentication module during token rotation."
        })
    }).then(res => res.json()).then(data => {
        console.log("Sandbox execution triggered:", data);
    }).catch(err => console.error("Sandbox trigger failed:", err));
}

// Launch from Sandbox Tab
function launchSandboxExecution() {
    const ticketId = document.getElementById("sandbox-ticket-id").value || "SCRUM-42";
    const bugDesc = document.getElementById("sandbox-desc").value || "Test directive execution.";
    
    document.getElementById("active-ticket").textContent = ticketId;
    const feedback = document.getElementById("sandbox-feedback");
    feedback.textContent = "⚙️ Dispatching A2A pipeline loop to SDLC Orchestrator...";
    
    fetch("/api/sandbox", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            ticket_key: ticketId,
            bug_description: bugDesc
        })
    }).then(res => res.json()).then(data => {
        feedback.textContent = "🚀 Pipeline launched! Switch to Workflow Topology tab to view live routing.";
        setTimeout(() => switchTab('topology'), 1500);
    }).catch(err => {
        feedback.textContent = "❌ Failed to connect to local Control Server.";
    });
}

// Reset UI Canvas State
function resetCanvas() {
    totalTokens = 0;
    document.getElementById("token-counter").textContent = "0";
    document.getElementById("status-orch").textContent = "Idle";
    document.getElementById("status-jira").textContent = "Ready";
    document.getElementById("status-eng").textContent = "Ready";
    document.getElementById("status-test").textContent = "Ready";
    document.querySelectorAll(".agent-node").forEach(el => el.classList.remove("active-routing", "success-status"));
    document.querySelectorAll(".connector-line").forEach(el => el.classList.remove("active"));
}

function clearLogs() {
    document.getElementById("stream-log").innerHTML = `
        <div class="log-entry">
            <span class="log-time">System</span>
            <span class="log-badge badge-init">CLEARED</span>
            <span class="log-source">Event Log</span>
            <span class="log-arrow">→</span>
            <span class="log-msg">Log buffer reset by developer.</span>
        </div>
    `;
    fetch("/api/clear").catch(e => console.log(e));
}
