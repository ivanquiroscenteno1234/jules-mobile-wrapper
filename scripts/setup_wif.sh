#!/bin/bash
set -e

# Hardcoded configuration
REPO="ivanquiroscenteno1234/jules-mobile-wrapper"
SERVICE_ACCOUNT_NAME="github-action-sa"
POOL_NAME="github-pool"
PROVIDER_NAME="github-provider"
DISPLAY_NAME="GitHub Actions Service Account"

echo "================================================================"
echo "      Workload Identity Federation Setup for GitHub Actions     "
echo "================================================================"

# Get Project ID
PROJECT_ID=$(gcloud config get-value project)
echo "Current Project ID: $PROJECT_ID"
echo "GitHub Repo: $REPO"
echo ""
echo "Press Enter to proceed with setup for this project..."
read

# 1. Enable APIs
echo "--> Enabling necessary APIs..."
gcloud services enable iamcredentials.googleapis.com
gcloud services enable cloudresourcemanager.googleapis.com
gcloud services enable sts.googleapis.com
gcloud services enable drive.googleapis.com

# 2. Create Service Account
echo "--> Checking Service Account..."
SA_EMAIL="${SERVICE_ACCOUNT_NAME}@${PROJECT_ID}.iam.gserviceaccount.com"

if gcloud iam service-accounts describe "$SA_EMAIL" > /dev/null 2>&1; then
    echo "    Service Account $SA_EMAIL already exists."
else
    echo "    Creating Service Account $SA_EMAIL..."
    gcloud iam service-accounts create "$SERVICE_ACCOUNT_NAME" \
        --display-name="$DISPLAY_NAME"
fi

# 3. Create Workload Identity Pool
echo "--> Checking Workload Identity Pool..."
if gcloud iam workload-identity-pools describe "$POOL_NAME" --location="global" > /dev/null 2>&1; then
    echo "    Pool $POOL_NAME already exists."
else
    echo "    Creating Pool $POOL_NAME..."
    gcloud iam workload-identity-pools create "$POOL_NAME" \
        --location="global" \
        --display-name="GitHub Actions Pool"
fi

POOL_ID=$(gcloud iam workload-identity-pools describe "$POOL_NAME" --location="global" --format="value(name)")

# 4. Create Workload Identity Provider
echo "--> Checking Workload Identity Provider..."
if gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" --location="global" --workload-identity-pool="$POOL_NAME" > /dev/null 2>&1; then
    echo "    Provider $PROVIDER_NAME already exists."
else
    echo "    Creating Provider $PROVIDER_NAME..."
    gcloud iam workload-identity-pools providers create "$PROVIDER_NAME" \
        --location="global" \
        --workload-identity-pool="$POOL_NAME" \
        --display-name="GitHub Actions Provider" \
        --attribute-mapping="google.subject=assertion.sub,attribute.actor=assertion.actor,attribute.repository=assertion.repository" \
        --issuer-uri="https://token.actions.githubusercontent.com"
fi

PROVIDER_ID=$(gcloud iam workload-identity-pools providers describe "$PROVIDER_NAME" --location="global" --workload-identity-pool="$POOL_NAME" --format="value(name)")

# 5. Bind Service Account to GitHub Repo
echo "--> Binding Service Account to GitHub Repo..."
# Allow specific repo to impersonate SA
gcloud iam service-accounts add-iam-policy-binding "$SA_EMAIL" \
    --role="roles/iam.workloadIdentityUser" \
    --member="principalSet://iam.googleapis.com/${POOL_ID}/attribute.repository/${REPO}" \
    --no-user-output-enabled

echo "================================================================"
echo "SETUP COMPLETE!"
echo "================================================================"
echo ""
echo "Please perform the following steps manually:"
echo ""
echo "1. SHARE GOOGLE DRIVE FOLDER:"
echo "   Go to your Google Drive folder: https://drive.google.com/drive/folders/1JXRr0gVfuxJZC2tBxoTtRjyshSzAn7UO"
echo "   Click 'Share' and add this email as an Editor:"
echo "   -> $SA_EMAIL"
echo ""
echo "2. ADD GITHUB SECRETS:"
echo "   Go to your GitHub Repo -> Settings -> Secrets and variables -> Actions"
echo "   Add the following secrets:"
echo ""
echo "   Name: GCP_SERVICE_ACCOUNT"
echo "   Value: $SA_EMAIL"
echo ""
echo "   Name: GCP_WORKLOAD_IDENTITY_PROVIDER"
echo "   Value: $PROVIDER_ID"
echo ""
echo "================================================================"
