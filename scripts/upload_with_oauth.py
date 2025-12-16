import os
import sys
import google.auth
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configuration
FOLDER_ID = "1JXRr0gVfuxJZC2tBxoTtRjyshSzAn7UO"
FILE_PATH = "temp_build/build/app/outputs/flutter-apk/app-release.apk"
FILE_NAME_PREFIX = "mobile_jules"

def upload_file():
    print("Preparing to upload...")

    # Get Secrets from Environment Variables
    client_id = os.environ.get("GDRIVE_CLIENT_ID")
    client_secret = os.environ.get("GDRIVE_CLIENT_SECRET")
    refresh_token = os.environ.get("GDRIVE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("Error: Missing one or more required secrets (GDRIVE_CLIENT_ID, GDRIVE_CLIENT_SECRET, GDRIVE_REFRESH_TOKEN).")
        sys.exit(1)

    # Create Credentials object manually using the refresh token
    creds = Credentials(
        None, # No access token yet
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
        scopes=['https://www.googleapis.com/auth/drive.file']
    )

    try:
        service = build('drive', 'v3', credentials=creds)
    except Exception as e:
        print(f"Failed to create Drive service: {e}")
        sys.exit(1)

    # Check if file exists
    if not os.path.exists(FILE_PATH):
        print(f"Error: File not found at {FILE_PATH}")
        sys.exit(1)

    # Generate a unique name using the GitHub Run Number if available
    run_number = os.environ.get("GITHUB_RUN_NUMBER", "0")
    file_name = f"{FILE_NAME_PREFIX}_{run_number}.apk"

    print(f"Uploading {FILE_PATH} as {file_name} to folder {FOLDER_ID}...")

    file_metadata = {
        'name': file_name,
        'parents': [FOLDER_ID]
    }

    media = MediaFileUpload(FILE_PATH, mimetype='application/vnd.android.package-archive')

    try:
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        print(f"Success! File ID: {file.get('id')}")
    except Exception as e:
        print(f"Upload failed: {e}")
        print("Tip: Check if the Folder ID is correct and if the authenticated user has write access to it.")
        sys.exit(1)

if __name__ == '__main__':
    upload_file()
