import os

from app.app_utils.config_helper import get_setting
from fastapi.openapi.models import (
    OAuth2,
    OAuthFlowAuthorizationCode,
    OAuthFlows,
)
from google.adk.auth.auth_credential import (
    AuthCredential,
    AuthCredentialTypes,
    OAuth2Auth,
)
from google.adk.auth.auth_tool import AuthConfig

# --- OAuth 2.0 Endpoints ---
# Atlassian requires the audience parameter
AUTHORIZATION_URL = "https://auth.atlassian.com/authorize?audience=api.atlassian.com&prompt=consent"
TOKEN_URL = "https://auth.atlassian.com/oauth/token"

# --- Scopes ---
SCOPES = {
    "read:jira-work": "Read Jira work",
    "manage:jira-project": "Manage Jira projects",
    "manage:jira-configuration": "Manage Jira configuration",
    "read:jira-user": "Read Jira users",
    "write:jira-work": "Write Jira work",
    "manage:jira-webhook": "Manage Jira webhooks",
    "manage:jira-data-provider": "Manage Jira data providers",
    "offline_access": "Offline access for refresh token",
}

# --- Token cache key must match the authorization resource ID exactly
TOKEN_CACHE_KEY = get_setting("AUTH_ID", "atlassian-oauth-auth-v6")

# --- OAuth scheme + credential (used only for local ADK Web UI dev) ---
AUTH_SCHEME = OAuth2(
    flows=OAuthFlows(
        authorizationCode=OAuthFlowAuthorizationCode(
            authorizationUrl=AUTHORIZATION_URL,
            tokenUrl=TOKEN_URL,
            scopes=SCOPES,
        )
    )
)

AUTH_CREDENTIAL = AuthCredential(
    auth_type=AuthCredentialTypes.OAUTH2,
    oauth2=OAuth2Auth(
        client_id=get_setting("OAUTH_CLIENT_ID", ""),
        client_secret=get_setting("OAUTH_CLIENT_SECRET", ""),
        redirect_uri="https://vertexaisearch.cloud.google.com/oauth-redirect",
    ),
)

AUTH_CONFIG = AuthConfig(
    auth_scheme=AUTH_SCHEME,
    raw_auth_credential=AUTH_CREDENTIAL,
)
