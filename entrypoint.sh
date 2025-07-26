#!/bin/sh

# This script is the entrypoint for the web container.
# It ensures the database is up-to-date before starting the main application.

# --- THIS IS THE FIX ---
# 'set -e' tells the script to exit immediately if any command fails.
set -e
# --- END FIX ---

# Apply database migrations
echo "Applying database migrations..."
flask db upgrade

# Start the Gunicorn server
echo "Starting Gunicorn..."
exec gunicorn --workers=4 --bind=0.0.0.0:5000 "app:create_app()"