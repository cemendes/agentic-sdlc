# sdlc-merger-v2

A platform-agnostic continuous delivery (CD) microservice agent designed for the SDLC Agent-to-Agent (A2A) orchestration pipeline.

## Capabilities
- **Automated Git Merging:** Pulls verified feature branches, performs clean `--no-ff` merges into release branches (`main`), handles conflict diagnosis, and pushes release commits to Google Secure Source Manager.
- **Platform-Agnostic Delivery:** Dynamically evaluates repository deployment instructions (`deploy_config.yaml`) and executes whatever custom build/deploy command is specified.
- **Live Endpoint Verification:** Executes post-deployment HTTP health smoketests against newly rolled-out URLs to guarantee operational availability before declaring completion.
