# Google Drive Upload Setup Guide

This guide explains how to set up the Google Drive integration for your GitHub Actions workflow. This will allow the generated APK files to be automatically uploaded to your specified Google Drive folder.

## Prerequisites

You need a Google account and a GitHub account.

## Step 1: Create a Google Cloud Project

1.  Go to the [Google Cloud Console](https://console.cloud.google.com/).
2.  Click on the project selector dropdown (top left) and click **"New Project"**.
3.  Give it a name (e.g., "Jules Mobile Builder") and click **"Create"**.
4.  Make sure your new project is selected.

## Step 2: Enable Google Drive API

1.  In the Google Cloud Console, open the main menu (hamburger icon) and go to **"APIs & Services" > "Library"**.
2.  Search for **"Google Drive API"**.
3.  Click on it and then click **"Enable"**.

## Step 3: Create a Service Account

1.  Go to **"APIs & Services" > "Credentials"**.
2.  Click **"+ CREATE CREDENTIALS"** and select **"Service account"**.
3.  Enter a name for the service account (e.g., "drive-uploader").
4.  Click **"Create and Continue"**.
5.  (Optional) For "Select a role", you can choose "Project > Editor" or leave it blank as we only need access to specific folders. Click **"Continue"**.
6.  Click **"Done"**.

## Step 4: Generate Service Account Key

1.  In the "Credentials" screen, look at the "Service Accounts" section.
2.  Click on the email address of the service account you just created (e.g., `drive-uploader@...`).
3.  Go to the **"Keys"** tab.
4.  Click **"ADD KEY"** > **"Create new key"**.
5.  Select **"JSON"** and click **"Create"**.
6.  A JSON file will be downloaded to your computer. **Keep this file safe!** It contains the credentials.

## Step 5: Share the Drive Folder

1.  Open the downloaded JSON key file and find the `"client_email"` field. Copy the email address inside it.
2.  Go to your Google Drive folder: [Target Folder](https://drive.google.com/drive/folders/1JXRr0gVfuxJZC2tBxoTtRjyshSzAn7UO).
3.  Click the folder name at the top or right-click the folder and select **"Share"**.
4.  Paste the service account email address you copied.
5.  Make sure the permission is set to **"Editor"** so it can upload files.
6.  Click **"Send"** (you can uncheck "Notify people" if you want).

## Step 6: Add Secrets to GitHub

1.  Go to your GitHub repository `jules-mobile-wrapper`.
2.  Click on **"Settings"** (top tab).
3.  In the left sidebar, click **"Secrets and variables"** > **"Actions"**.
4.  Click **"New repository secret"**.
    *   **Name**: `GDRIVE_CREDENTIALS`
    *   **Secret**: Open your downloaded JSON key file with a text editor, copy the *entire* content, and paste it here.
    *   Click **"Add secret"**.

*Note: The folder ID `1JXRr0gVfuxJZC2tBxoTtRjyshSzAn7UO` is already configured in the workflow file, so you don't need to add it as a secret.*

## Done!

Now, every time you push code to the `main` or `master` branch, the GitHub Action will:
1.  Build the Flutter APK.
2.  Upload the APK file to your Google Drive folder.
