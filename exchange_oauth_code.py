#!/usr/bin/env python3
"""
OAuth Token Exchange Helper for Atlassian Jira.
Exchanges an authorization code for an Atlassian Access Token.
"""
import os
import sys
import json
import requests

CLIENT_ID = "8UzalOgg5Orkkhb3seKsyVEeNzGvc1LG"
CLIENT_SECRET = os.environ.get("OAUTH_CLIENT_SECRET", "<YOUR_OAUTH_CLIENT_SECRET>")
REDIRECT_URI = "https://vertexaisearch.cloud.google.com/oauth-redirect"
TOKEN_FILE = os.path.expanduser("~/.jira_oauth_token.json")

def print_auth_url():
    auth_url = (
        f"https://auth.atlassian.com/authorize?"
        f"audience=api.atlassian.com&"
        f"client_id={CLIENT_ID}&"
        f"scope=read%3Ajira-work%20write%3Ajira-work%20manage%3Ajira-project%20read%3Ajira-user%20offline_access&"
        f"redirect_uri={REDIRECT_URI}&"
        f"response_type=code&"
        f"prompt=consent"
    )
    print("\n" + "=" * 80)
    print("🔑 ATLASSIAN JIRA OAUTH AUTHENTICATION")
    print("=" * 80)
    print("\n1. Open this URL in your browser to authorize:")
    print(f"\n   {auth_url}\n")
    print("2. After clicking 'Accept', copy the 'code=...' parameter from your browser URL bar.")
    print("=" * 80 + "\n")

def exchange_code(code: str):
    print(f"🔄 Exchanging code for Access Token...")
    payload = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "code": code.strip(),
        "redirect_uri": REDIRECT_URI
    }
    headers = {"Content-Type": "application/json"}
    res = requests.post("https://auth.atlassian.com/oauth/token", json=payload, headers=headers)
    
    if res.status_code == 200:
        data = res.json()
        with open(TOKEN_FILE, "w") as f:
            json.dump(data, f, indent=2)
        print(f"✅ SUCCESS! OAuth token saved to {TOKEN_FILE}")
        print(f"🔑 Access Token: {data.get('access_token')[:25]}...")
        return data.get("access_token")
    else:
        print(f"❌ Error exchanging code: {res.status_code} - {res.text}")
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print_auth_url()
        print("Usage to save token:")
        print("  python3 exchange_oauth_code.py <authorization_code>")
    else:
        exchange_code(sys.argv[1])
