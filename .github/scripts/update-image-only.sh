#!/bin/bash
# This script updates only the Docker image tags without touching environment variables

APP_ID=$1
NEW_TAG=$2

if [ -z "$APP_ID" ] || [ -z "$NEW_TAG" ]; then
    echo "Usage: $0 <app-id> <new-tag>"
    exit 1
fi

echo "Updating app $APP_ID to use tag $NEW_TAG"

# Update only the web service image
doctl apps update-component $APP_ID \
    --component-name attackacrack-web \
    --spec-type service \
    --image-tag $NEW_TAG

# Update only the worker image
doctl apps update-component $APP_ID \
    --component-name attackacrack-worker \
    --spec-type worker \
    --image-tag $NEW_TAG

echo "Image tags updated successfully"