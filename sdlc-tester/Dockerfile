FROM us-central1-docker.pkg.dev/your-project-id/agent-platform-containers/agent-base:latest

WORKDIR /app

# Copy agent application source
COPY app/ /app/app/
COPY pyproject.toml /app/

# Expose server port
EXPOSE 8080

CMD ["python", "-m", "app.agent_runtime_app"]
