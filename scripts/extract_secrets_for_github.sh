#!/bin/bash
# Script to extract environment variable values for GitHub Secrets
# This makes it easy to copy/paste values into GitHub repository settings

echo "=================================================="
echo "Environment Variables for GitHub Secrets"
echo "=================================================="
echo ""
echo "Go to: https://github.com/mrjmd/attackacrack/settings/secrets/actions"
echo "Click 'New repository secret' for each of these:"
echo ""
echo "=================================================="

# Source the .env file
if [ -f .env ]; then
    source .env
else
    echo "ERROR: .env file not found!"
    exit 1
fi

# List of required secrets
declare -a secrets=(
    "SECRET_KEY"
    "REDIS_URL"
    "CELERY_BROKER_URL"
    "CELERY_RESULT_BACKEND"
    "OPENPHONE_API_KEY"
    "OPENPHONE_WEBHOOK_SIGNING_KEY"
    "OPENPHONE_PHONE_NUMBER"
    "OPENPHONE_PHONE_NUMBER_ID"
    "ENCRYPTION_KEY"
    "GEMINI_API_KEY"
    "GOOGLE_CLIENT_ID"
    "GOOGLE_CLIENT_SECRET"
    "GOOGLE_PROJECT_ID"
    "PROPERTY_RADAR_API_KEY"
    "QUICKBOOKS_CLIENT_ID"
    "QUICKBOOKS_CLIENT_SECRET"
    "QUICKBOOKS_REDIRECT_URI"
    "QUICKBOOKS_SANDBOX"
    "SMARTLEAD_API_KEY"
)

# Print each secret name and value
for secret in "${secrets[@]}"; do
    value="${!secret}"
    if [ -n "$value" ]; then
        echo ""
        echo "Secret Name: $secret"
        echo "Secret Value:"
        echo "$value"
        echo "--------------------------------------------------"
    else
        echo ""
        echo "⚠️  WARNING: $secret is not set in .env file"
        echo "--------------------------------------------------"
    fi
done

echo ""
echo "=================================================="
echo "IMPORTANT: Copy each value carefully!"
echo "Make sure to add ALL secrets before pushing the code."
echo "=================================================="