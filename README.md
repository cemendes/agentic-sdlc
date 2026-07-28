# agentic-sdlc

Autonomous multi-agent system built with Python, Google Cloud Agent Platform (Vertex AI Reasoning Engine), Google Cloud Secure Source Manager, and an external Jira Cloud instance.

It automates end-to-end software development workflows across enterprise infrastructure: listening for Jira ticket updates, cloning code from Secure Source Manager, scaffolding feature/fix branches, applying code changes with Gemini, running automated unit tests, and merging to `main` with live deployment.

---

## Architecture & System Overview

```
                      +-------------------+
                      | SDLC Orchestrator |
                      +---------+---------+
                                |
        +-----------------------+-----------------------+
        |                       |                       |
+-------v-------+       +-------v-------+       +-------v-------+
|  Engineer     |       |    Tester     |       |    Merger     |
|  Agent        |       |    Agent      |       |    Agent      |
+---------------+       +---------------+       +---------------+
        |                       |                       |
        +-----------------------+-----------------------+
                                |
                     +----------v----------+
                     | Jira Connector Agent|
                     +---------------------+
```

### Agent Roles & Workflows

1. **SDLC Orchestrator (`sdlc-orchestrator`)**  
   Acts as the central controller on Agent Platform. It parses Jira ticket requests and coordinates task execution across downstream agents using agent-to-agent (A2A) protocol calls.

2. **Jira Connector (`jira-mcp-agent`)**  
   Connects to an external Jira Cloud instance using OAuth 2.0 (3LO). It handles ticket queries, updates status transitions (e.g. `In Progress` to `In Review`), and posts execution trace logs as comments.

3. **Engineer Agent (`sdlc-engineer`)**  
   Interacts directly with Google Cloud Secure Source Manager. It checks out the main codebase, creates isolated Git fix branches, and applies code modifications requested in the Jira issue.

4. **Tester Agent (`sdlc-tester`)**  
   Validates generated code changes before merge. It executes local test suites and performs automated HTTP health checks against deployed staging endpoints.

5. **Merger & Deployer Agent (`sdlc-merger`)**  
   Handles branch integration on Secure Source Manager. Once tests pass, it merges the fix branch into `main`, cleans up temporary remote branches, and triggers application deployment.

---

## Project Structure

```
.
├── sdlc-orchestrator/        # Central orchestrator deployed to Agent Platform
├── jira-mcp-agent/           # Jira OAuth 2.0 connector & ticket integration agent
├── sdlc-engineer/           # Git & code modification agent (Secure Source Manager)
├── sdlc-tester/             # Unit test execution & post-deploy health check agent
├── sdlc-merger/             # Branch merger & deployment automation agent
├── a2a-mission-control/     # Dashboard for monitoring agent-to-agent telemetry
├── sdlc-test-repo-local/    # Sample application repository hosted on Secure Source Manager
├── deploy_all_parallel_v2.py # Parallel deployment script for Vertex AI Agent Runtime
└── test_pipeline_local.py   # Local pipeline runner for testing agents end-to-end
```

---

## Setup & Prerequisites

### Infrastructure Requirements
- **Google Cloud Platform**: Active project with Vertex AI Reasoning Engine (Agent Runtime) and Secure Source Manager enabled.
- **Jira Cloud**: External Jira instance with an OAuth 2.0 (3LO) integration app registered in Atlassian Developer Console.
- **Local Environment**: Python 3.11+ and `gcloud` CLI authenticated with your GCP account.

### 1. Secrets Configuration
Copy the secrets template in each agent directory:

```bash
cp sdlc-orchestrator/app/secrets.example.json sdlc-orchestrator/app/secrets.json
cp jira-mcp-agent/app/secrets.example.json jira-mcp-agent/app/secrets.json
```

Configure `secrets.json` with your OAuth keys and GCP project details:

```json
{
  "OAUTH_CLIENT_ID": "your-client-id.apps.googleusercontent.com",
  "OAUTH_CLIENT_SECRET": "your-client-secret",
  "JIRA_SITE_URL": "https://your-domain.atlassian.net/",
  "GOOGLE_CLOUD_PROJECT": "your-gcp-project-id",
  "LOCATION": "us-central1"
}
```

### 2. Local Pipeline Execution
Run the full multi-agent pipeline locally against a target Jira ticket:

```bash
python3 test_pipeline_local.py --ticket SCRUM-11 --prompt "Fix validation logic in index.html"
```

### 3. Deploying to Agent Platform
Deploy all five agents concurrently to GCP Vertex AI Reasoning Engine:

```bash
python3 deploy_all_parallel_v2.py
```

### 4. Monitoring Telemetry (Mission Control)
Start the local dashboard to observe live agent-to-agent messages and tool execution traces:

```bash
./run_dashboard.sh
```

Open `http://localhost:5050` in your browser.
