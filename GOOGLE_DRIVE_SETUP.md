# Google Drive Upload Setup (OAuth 2.0 Method)

We are switching to **OAuth 2.0** because standard Service Accounts have a "Storage Quota" of 0 bytes, which prevents them from uploading files to personal Google Drive folders. By using OAuth, the script will act **as you**, using your own storage quota.

## Prerequisites
1. You must have a Google Cloud Project.
2. You must have the Google Drive folder created: `https://drive.google.com/drive/folders/1JXRr0gVfuxJZC2tBxoTtRjyshSzAn7UO`

## Step 1: Create OAuth Credentials

1. Go to **[APIs & Services > OAuth consent screen](https://console.cloud.google.com/apis/credentials/consent)**.
2. Select **External** and click **Create**.
3. Fill in required fields:
   *   **App name:** "GitHub Actions Upload"
   *   **User support email:** (Your email)
   *   **Developer contact information:** (Your email)
   *   Click **Save and Continue**.
4. **Scopes:** Click **Add or Remove Scopes**.
   *   Search for `drive.file` and select it (`.../auth/drive.file`).
   *   Click **Update**, then **Save and Continue**.
5. **Test Users:** Add your own email address. Click **Save and Continue**.
6. **Publish App:**
   *   Back on the dashboard, click **PUBLISH APP** (under "Publishing Status").
   *   Confirm by clicking **Confirm**.
   *   *Note: This prevents the token from expiring in 7 days. You will see a warning later because the app isn't verified, which is fine for personal use.*

## Step 2: Create Client ID

1. Go to **[APIs & Services > Credentials](https://console.cloud.google.com/apis/credentials)**.
2. Click **+ CREATE CREDENTIALS** > **OAuth client ID**.
3. **Application type:** Select **Desktop app**.
4. **Name:** "GitHub Actions".
5. Click **Create**.
6. A popup will appear. **Copy** the **Client ID** and **Client Secret**. Save them specifically.

## Step 3: Generate Refresh Token

You need to authorize the app once to get a "Refresh Token" that allows GitHub Actions to access your Drive forever.

1. Open **[Google Cloud Shell](https://console.cloud.google.com/)** (terminal icon in top right).
2. Paste the following command to create a helper script (copy the whole block):

```bash
cat << 'EOF' > get_token.py
import json
from google_auth_oauthlib.flow import InstalledAppFlow

# CONFIGURATION
# ------------------------------------------------------------------
# REPLACE THESE TWO VALUES WITH YOUR COPIED ID AND SECRET
CLIENT_ID = "PASTE_YOUR_CLIENT_ID_HERE"
CLIENT_SECRET = "PASTE_YOUR_CLIENT_SECRET_HERE"
# ------------------------------------------------------------------

SCOPES = ['https://www.googleapis.com/auth/drive.file']

def get_refresh_token():
    config = {
        "installed": {
            "client_id": CLIENT_ID,
            "project_id": "files-upload",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_secret": CLIENT_SECRET,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"]
        }
    }

    flow = InstalledAppFlow.from_client_config(config, SCOPES)
    creds = flow.run_console()

    print("\n\n========================================================")
    print("SUCCESS! HERE IS YOUR REFRESH TOKEN:")
    print("========================================================")
    print(creds.refresh_token)
    print("========================================================")

if __name__ == '__main__':
    get_refresh_token()
EOF
```

3. **Edit the script** to add your Client ID and Secret:
   *   Type `nano get_token.py`
   *   Use arrow keys to find `PASTE_YOUR_CLIENT_ID_HERE` and replace it with your actual Client ID.
   *   Replace `PASTE_YOUR_CLIENT_SECRET_HERE` with your actual Client Secret.
   *   Press **Ctrl+O**, **Enter** to save.
   *   Press **Ctrl+X** to exit.

4. **Run the script:**
   ```bash
   pip3 install google-auth-oauthlib
   python3 get_token.py
   ```
5. **Follow the prompts:**
   *   It will show a URL. Click it.
   *   Sign in with your Google account.
   *   **Warning:** You will see "Google hasn't verified this app". Click **Advanced** > **Go to GitHub Actions Upload (unsafe)**.
   *   Click **Continue** / **Allow**.
   *   Copy the code displayed and paste it back into the Cloud Shell terminal.
   *   Press Enter.
   *   **Copy the Refresh Token** it prints out.

## Step 4: Add GitHub Secrets

1. Go to your GitHub Repo: **Settings** > **Secrets and variables** > **Actions**.
2. Add the following 3 secrets:

   *   **Name:** `GDRIVE_CLIENT_ID`
       *   **Value:** (Your Client ID)
   *   **Name:** `GDRIVE_CLIENT_SECRET`
       *   **Value:** (Your Client Secret)
   *   **Name:** `GDRIVE_REFRESH_TOKEN`
       *   **Value:** (The long token starting with `1//...`)

## Step 5: Verify

Once these secrets are added, go to the **Actions** tab and re-run the failed job. It should now successfully upload to your Drive!
