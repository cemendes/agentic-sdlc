# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import logging
import os
from typing import Any, Optional

import vertexai
from dotenv import load_dotenv
from google.adk.artifacts import GcsArtifactService, InMemoryArtifactService
from google.cloud import logging as google_cloud_logging
from vertexai.agent_engines.templates.adk import AdkApp

from app.agent import app as adk_app
from app.app_utils.telemetry import setup_telemetry
from app.app_utils.typing import Feedback

# Load environment variables from .env file at runtime only if running locally
if not os.environ.get("K_SERVICE") and not os.environ.get("AIP_MODE"):
    load_dotenv()


class AgentEngineApp(AdkApp):
    def stream_query(
        self,
        *,
        message: Any,
        user_id: str,
        session_id: Optional[str] = None,
        run_config: Optional[dict[str, Any]] = None,
        access_token: Optional[str] = None,
        **kwargs
    ):
        if access_token:
            os.environ[f"JIRA_ACCESS_TOKEN_{user_id}"] = access_token
        
        run_config = run_config or {}
        if isinstance(run_config, dict):
            run_config["max_llm_calls"] = run_config.get("max_llm_calls", 15)
            
        return super().stream_query(
            message=message,
            user_id=user_id,
            session_id=session_id,
            run_config=run_config,
        )

    def set_up(self) -> None:
        """Initialize the agent engine app with logging and telemetry."""
        vertexai.init()
        setup_telemetry()
        super().set_up()
        logging.basicConfig(level=logging.INFO)
        logging_client = google_cloud_logging.Client()
        self.logger = logging_client.logger(__name__)
        if gemini_location:
            os.environ["GOOGLE_CLOUD_LOCATION"] = gemini_location

    def register_feedback(self, feedback: dict[str, Any]) -> None:
        """Collect and log feedback."""
        feedback_obj = Feedback.model_validate(feedback)
        self.logger.log_struct(feedback_obj.model_dump(), severity="INFO")

    def register_operations(self) -> dict[str, list[str]]:
        """Registers the operations of the Agent."""
        operations = super().register_operations()
        operations[""] = [*operations.get("", []), "register_feedback"]
        return operations


def build_artifact_service():
    bucket = os.environ.get("LOGS_BUCKET_NAME")
    if bucket:
        return GcsArtifactService(bucket_name=bucket)
    return InMemoryArtifactService()

gemini_location = os.environ.get("GOOGLE_CLOUD_LOCATION")
agent_runtime = AgentEngineApp(
    app=adk_app,
    artifact_service_builder=build_artifact_service,
)
