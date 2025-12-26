"""
Generate a new Google Drive OAuth Refresh Token.

Run this script locally to get a new refresh token, then update
the GDRIVE_REFRESH_TOKEN secret in GitHub.

Prerequisites:
    pip install google-auth google-auth-oauthlib

Usage:
    1. Download your OAuth credentials from Google Cloud Console
       (APIs & Services > Credentials > Your OAuth 2.0 Client > Download JSON)
    2. Save as 'client_secrets.json' in the same folder as this script
    3. Run: python generate_refresh_token.py
    4. Copy the refresh token and update your GitHub Secret
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def main():
    # Check for client_secrets.json
    if not os.path.exists('client_secrets.json'):
        print("ERROR: client_secrets.json not found!")
        print("\nTo get this file:")
        print("1. Go to Google Cloud Console: https://console.cloud.google.com/")
        print("2. Navigate to: APIs & Services > Credentials")
        print("3. Find your OAuth 2.0 Client ID")
        print("4. Click the download icon to download the JSON")
        print("5. Save it as 'client_secrets.json' in this folder")
        return

    print("Starting OAuth flow...")
    print("A browser window will open. Sign in with your Google account.\n")

    flow = InstalledAppFlow.from_client_secrets_file('client_secrets.json', SCOPES)
    
    # Run the OAuth flow - will open browser
    creds = flow.run_local_server(port=8080)

    print("\n" + "="*60)
    print("SUCCESS! Here are your credentials:")
    print("="*60)
    print(f"\nRefresh Token (copy this to GDRIVE_REFRESH_TOKEN):\n{creds.refresh_token}")
    print(f"\nClient ID:\n{creds.client_id}")
    print(f"\nClient Secret:\n{creds.client_secret}")
    print("\n" + "="*60)
    print("\nNext steps:")
    print("1. Go to GitHub Repo > Settings > Secrets and variables > Actions")
    print("2. Update GDRIVE_REFRESH_TOKEN with the new refresh token above")
    print("3. Re-run the failed workflow")
    print("="*60)

if __name__ == '__main__':
    main()
