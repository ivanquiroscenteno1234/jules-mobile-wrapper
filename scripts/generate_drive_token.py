import json
import os
import sys

# Try to import google_auth_oauthlib
try:
    from google_auth_oauthlib.flow import InstalledAppFlow
except ImportError:
    print("Error: 'google-auth-oauthlib' is not installed.")
    print("Please install it by running: pip install google-auth-oauthlib")
    sys.exit(1)

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_refresh_token():
    print("--- Google Drive OAuth Token Generator ---")
    print("This script will help you generate a Refresh Token for GitHub Actions.\n")

    client_id = input("Enter your OAuth Client ID: ").strip()
    if not client_id:
        print("Client ID is required.")
        return

    client_secret = input("Enter your OAuth Client Secret: ").strip()
    if not client_secret:
        print("Client Secret is required.")
        return

    config = {
        "installed": {
            "client_id": client_id,
            "project_id": "files-upload", # Arbitrary project ID for the config structure
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": client_secret,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
        }
    }

    print("\nStarting OAuth flow...")
    print("A browser window should open (or you'll get a link) to authorize the app.")
    print("IMPORTANT: If you see 'Google hasn't verified this app', click 'Advanced' -> 'Go to... (unsafe)'.")

    try:
        flow = InstalledAppFlow.from_client_config(config, SCOPES)
        # run_local_server works best on local machines, run_console for cloud shell
        # We'll try run_local_server first, fallback or ask user preference?
        # Actually, for widest compatibility (including cloud shell or headless), console is safer
        # but less convenient locally. Let's default to console flow for reliability.
        creds = flow.run_console()

        print("\n\n========================================================")
        print("SUCCESS! HERE ARE YOUR VALUES FOR GITHUB SECRETS:")
        print("========================================================")
        print(f"GDRIVE_CLIENT_ID:     {client_id}")
        print(f"GDRIVE_CLIENT_SECRET: {client_secret}")
        print(f"GDRIVE_REFRESH_TOKEN: {creds.refresh_token}")
        print("========================================================")
        print("Go to your GitHub Repo -> Settings -> Secrets and variables -> Actions")
        print("And add these 3 secrets exactly as shown above.")

    except Exception as e:
        print(f"\nError during authentication: {e}")

if __name__ == '__main__':
    get_refresh_token()
