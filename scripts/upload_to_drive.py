import os
import sys
import google.auth
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# Configuration
FOLDER_ID = "1JXRr0gVfuxJZC2tBxoTtRjyshSzAn7UO"
FILE_PATH = "mobile_jules_client/build/app/outputs/flutter-apk/app-release.apk"
FILE_NAME = f"mobile_jules_release.apk"

def upload_file():
    print("Authenticating...")
    # Use the default credentials (provided by WIF in GitHub Actions)
    # We specifically need the Drive scope
    scopes = ['https://www.googleapis.com/auth/drive']
    creds, project = google.auth.default(scopes=scopes)

    print(f"Authenticated with project: {project}")

    service = build('drive', 'v3', credentials=creds)

    # Check if file exists
    if not os.path.exists(FILE_PATH):
        print(f"Error: File not found at {FILE_PATH}")
        sys.exit(1)

    print(f"Uploading {FILE_PATH} to folder {FOLDER_ID}...")

    file_metadata = {
        'name': FILE_NAME,
        'parents': [FOLDER_ID]
    }

    media = MediaFileUpload(FILE_PATH, mimetype='application/vnd.android.package-archive')

    file = service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id'
    ).execute()

    print(f"File ID: {file.get('id')} uploaded successfully.")

if __name__ == '__main__':
    try:
        upload_file()
    except Exception as e:
        print(f"Upload failed: {e}")
        sys.exit(1)
