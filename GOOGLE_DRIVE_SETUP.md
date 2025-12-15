# Google Drive Upload Setup (Bypassing Key Restrictions)

We have set up an automated system to build your Android App and upload it to your Google Drive folder whenever you push changes to GitHub.

Because your Google Cloud account has a restriction that prevents creating "Service Account Keys" (`constraints/iam.disableServiceAccountKeyCreation`), we are using a more modern and secure method called **Workload Identity Federation**.

## Prerequisites
1. You must have a Google Cloud Project.
2. You must have the Google Drive folder created: `https://drive.google.com/drive/folders/1JXRr0gVfuxJZC2tBxoTtRjyshSzAn7UO`

## Step 1: Run the Setup Script in Google Cloud Shell

We have prepared a script that automatically configures everything for you.

1. Go to the [Google Cloud Console](https://console.cloud.google.com/).
2. Click the **Activate Cloud Shell** icon (a terminal prompt symbol >_) in the top right toolbar.
3. Wait for the terminal to provision and connect.
4. Copy and paste the following commands into the Cloud Shell terminal and press Enter:

```bash
# Download the setup script directly from your repo (or create it)
cat << 'EOF' > setup_wif.sh
#!/bin/bash
set -e

# Configuration
REPO="ivanquiroscenteno1234/jules-mobile-wrapper"
SERVICE_ACCOUNT_NAME="github-action-sa"
POOL_NAME="github-pool"
PROVIDER_NAME="github-provider"

echo "Setting up Workload Identity Federation for: $REPO"
PROJECT_ID=$(gcloud config get-value project)
echo "Project ID: $PROJECT_ID"

# Enable APIs
gcloud services enable iamcredentials.googleapis.com cloudresourcemanager.googleapis.com sts.googleapis.com drive.googleapis.com

# Create Service Account
SA_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"
if ! gcloud iam service-accounts describe "$SA_EMAIL" > /dev/null 2>&1; then
    gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" --display-name="GitHub Actions Service Account"
fi

# Create Pool & Provider
if ! gcloud iam workload-identity-pools describe "$POOL_NAME" --location="global" > /dev/null 2>&1; then
    gcloud iam workload-identity-pools create "$POOL_NAME" --location="global" --display-name="GitHub Actions Pool"
fi
POOL_ID=$(gcloud iam workload-identity-pools describe "$POOL_NAME" --location="global" --format="value(name)")

if ! gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" --location="global" --workload-identity-pool="$POOL_NAME" > /dev/null 2>&1; then
    gcloud iam workload-identity-pools providers create "$PROVIDER_NAME" --location="global" --workload-identity-pool="$POOL_NAME" \
    --display-name="GitHub Actions Provider" \
    --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
    --issuer-uri="https://token.actions.githubusercontent.com"
fi
PROVIDER_ID=$(gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" --location="global" --workload-identity-pool="$POOL_NAME" --format="value(name)")

# Bind Repo
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/${REPO}" \
    --no-user-output-enabled

echo ""
echo "--------------------------------------------------------"
echo "SETUP COMPLETE. PLEASE SAVE THESE VALUES:"
echo "--------------------------------------------------------"
echo "1. Service Account Email: $SA_EMAIL"
echo "2. Provider ID:           $PROVIDER_ID"
echo "--------------------------------------------------------"
EOF

# Run the script
bash setup_wif.sh
```

## Step 2: Share the Google Drive Folder

1. Copy the **Service Account Email** output by the script (e.g., `github-action-sa@your-project.iam.gserviceaccount.com`).
2. Go to your [Google Drive Folder](https://drive.google.com/drive/folders/1JXRr0gVfuxJZC2tBxoTtRjyshSzAn7UO).
3. Click the dropdown arrow next to the folder name > **Share**.
4. Paste the email address into the "Add people and groups" field.
5. Ensure the permission is set to **Editor**.
6. Uncheck "Notify people" (optional, as it's a robot).
7. Click **Send** (or Share).

## Step 3: Add GitHub Secrets

1. Go to your GitHub Repository: `https://github.com/ivanquiroscenteno1234/jules-mobile-wrapper`
2. Navigate to **Settings** > **Secrets and variables** > **Actions**.
3. Click **New repository secret**.
4. Add the first secret:
   *   **Name:** `GCP_SERVICE_ACCOUNT`
   *   **Value:** (Paste the Service Account Email from Step 1)
5. Click **Add secret**.
6. Click **New repository secret** again.
7. Add the second secret:
   *   **Name:** `GCP_WORKLOAD_IDENTITY_PROVIDER`
   *   **Value:** (Paste the Provider ID from Step 1, it looks like `projects/123.../locations/global/workloadIdentityPools/...`)
8. Click **Add secret**.

## Step 4: Verify

Once these secrets are added, the next time you push code to `main`, the "Build and Upload" action will run automatically.
