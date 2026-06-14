#!/usr/bin/env python3
"""One-time: get a YouTube refresh token for uploading.

Prereqs:
  1. Go to https://console.cloud.google.com/ -> create a project (free).
  2. Enable "YouTube Data API v3".
  3. APIs & Services -> Credentials -> Create OAuth client ID -> type "Desktop app".
  4. Download the client JSON, or just grab the Client ID + Secret.
  5. OAuth consent screen: set to "External", add yourself as a Test user.

Then run:
  pip install google-auth-oauthlib
  python scripts/get_youtube_token.py

It opens a browser, you approve, and it prints the 3 values to put in your
.env (locally) or GitHub Secrets (for the cloud).
"""
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main():
    client_id = input("Paste your OAuth Client ID: ").strip()
    client_secret = input("Paste your OAuth Client Secret: ").strip()

    config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    creds = flow.run_local_server(port=0, prompt="consent", access_type="offline")

    print("\n=== Add these to .env / GitHub Secrets ===")
    print(f"YOUTUBE_CLIENT_ID={client_id}")
    print(f"YOUTUBE_CLIENT_SECRET={client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN={creds.refresh_token}")


if __name__ == "__main__":
    main()
