# Google Drive Upload Setup (Service Account Key Method)

We have set up an automated system to build your Android App and upload it to your Google Drive folder whenever you push changes to GitHub.

Since you have successfully acquired the **Organization Policy Administrator** role, we will use the standard "Service Account Key" method.

## Prerequisites
1. You must have a Google Cloud Project.
2. You must have the Google Drive folder created: `https://drive.google.com/drive/folders/1JXRr0gVfuxJZC2tBxoTtRjyshSzAn7UO`

## Step 1: Disable the "Disable Service Account Key Creation" Policy

Now that you have the correct permissions, you must unlock the ability to create keys.

1. Go to the **[Organization Policies](https://console.cloud.google.com/iam-admin/orgpolicies)** page in the Google Cloud Console.
2. In the filter box at the top, type `disableServiceAccountKeyCreation` and select **Constraints: iam.disableServiceAccountKeyCreation**.
3. Click the **Edit** button (pencil icon).
4. Select **Manage Policy**.
5. Under **Policy enforcement**, select **Off** (or "Not enforced").
   * *Note: If "Off" isn't an option, select "Customize", then "Rules", and set "Enforcement" to "Off".*
6. Click **Save**.

## Step 2: Create a Service Account and Key

1. Go to **[IAM & Admin > Service Accounts](https://console.cloud.google.com/iam-admin/serviceaccounts)**.
2. Click **+ CREATE SERVICE ACCOUNT**.
3. **Service account details:**
   *   Name: `github-upload-sa`
   *   Click **Create and Continue**.
4. **Grant this service account access to project:**
   *   Role: **Editor** (or specifically "Service Account Token Creator" + "Drive File Editor" if you prefer granularity, but Editor is easiest).
   *   Click **Done**.
5. Locate the new service account in the list (`github-upload-sa@...`).
6. Click the **three dots** (Actions) > **Manage keys**.
7. Click **ADD KEY** > **Create new key**.
8. Select **JSON**.
9. Click **Create**.
   *   A file (e.g., `project-id-12345.json`) will download to your computer. **Keep this file safe.**

## Step 3: Share the Google Drive Folder

1. Open your downloaded JSON file and look for the `"client_email"` field (e.g., `github-upload-sa@your-project.iam.gserviceaccount.com`). Copy this email.
2. Go to your [Google Drive Folder](https://drive.google.com/drive/folders/1JXRr0gVfuxJZC2tBxoTtRjyshSzAn7UO).
3. Click the dropdown arrow next to the folder name > **Share**.
4. Paste the email address into the "Add people and groups" field.
5. Ensure the permission is set to **Editor**.
6. Click **Send**.

## Step 4: Add the GitHub Secret

1. Open the downloaded JSON file in a text editor (Notepad, TextEdit, VS Code) and **copy the entire content**.
2. Go to your GitHub Repository: `https://github.com/ivanquiroscenteno1234/jules-mobile-wrapper`
3. Navigate to **Settings** > **Secrets and variables** > **Actions**.
4. Click **New repository secret**.
5. **Name:** `GDRIVE_CREDENTIALS`
6. **Value:** (Paste the entire JSON content here)
7. Click **Add secret**.

## Step 5: Verify

Once the secret is added, the next time you push code to `main` (or re-run the failed job), the build will succeed and upload the APK to your Drive.
