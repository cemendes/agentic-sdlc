# agentic-sdlc

Autonomous multi-agent system built with Python, Google Cloud Vertex AI Reasoning Engine (Agent Runtime), and Jira OAuth.

It automates software development tasks by orchestrating specialized AI agents: processing Jira ticket updates, scaffolding feature/fix branches, modifying code, running tests, and merging to `main` with automatic deployment.

---

## Architecture & Agent Roles

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

1. **SDLC Orchestrator (`sdlc-orchestrator`)**  
   Routes incoming tasks and coordinates execution across specialized agents.

2. **Jira Connector (`jira-mcp-agent`)**  
   Handles Jira OAuth authentication, fetches ticket details, updates issue statuses, and posts progress comments.

3. **Engineer Agent (`sdlc-engineer`)**  
   Generates fix/feature branches in Git and implements required code changes.

4. **Tester Agent (`sdlc-tester`)**  
   Executes unit tests and validates health checks against the updated code.

5. **Merger & Deployer Agent (`sdlc-merger`)**  
   Merges approved branches into `main` and triggers deployment.

---

## Project Structure

```
.
├── sdlc-orchestrator/        # Central orchestration agent
├── jira-mcp-agent/           # Jira OAuth & API integration agent
├── sdlc-engineer/           # Code modification & branch creation agent
├── sdlc-tester/             # Unit testing & verification agent
├── sdlc-merger/             # Branch merger & deployment agent
├── a2a-mission-control/     # Web dashboard for real-time agent telemetry
├── sdlc-test-repo-local/    # Sample target application
├── deploy_all_parallel_v2.py # Parallel deployment script for Vertex AI Agent Runtime
└── test_pipeline_local.py   # Local execution runner for testing pipelines
```

---

## Setup & Configuration

### Prerequisites
- Python 3.11+
- Google Cloud SDK (`gcloud` CLI initialized with active GCP project)
- Atlassian Developer app configured with OAuth 2.0 (3LO)

### 1. Secrets Configuration
Copy the secrets template in each agent directory:

```bash
cp sdlc-orchestrator/app/secrets.example.json sdlc-orchestrator/app/secrets.json
cp jira-mcp-agent/app/secrets.example.json jira-mcp-agent/app/secrets.json
```

Update `secrets.json` with your credentials:

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
Run a local test of the multi-agent pipeline against a Jira ticket:

```bash
python3 test_pipeline_local.py --ticket SCRUM-11 --prompt "Fix validation logic in index.html"
```

### 3. Deployment to Vertex AI Agent Runtime
Deploy all agents in parallel to GCP Vertex AI Reasoning Engine:

```bash
python3 deploy_all_parallel_v2.py
```

### 4. Mission Control Dashboard
Launch the web UI to monitor live inter-agent communication:

```bash
./run_dashboard.sh
```

Navigate to `http://localhost:5050` to view the active telemetry feed.
