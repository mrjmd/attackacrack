#!/bin/sh

# This script is the entrypoint for the web container.
# It ensures the database is up-to-date before starting the main application.

# --- THIS IS THE FIX ---
# 'set -e' tells the script to exit immediately if any command fails.
set -e
# --- END FIX ---

# Apply database migrations
echo "Applying database migrations..."
# Set a flag to skip validation during migrations
export SKIP_ENV_VALIDATION=1
flask db upgrade
unset SKIP_ENV_VALIDATION

# Start the Gunicorn server
# Set timeout with environment variable, default to 300 seconds (5 minutes) for CSV imports
GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-300}
GUNICORN_WORKERS=${GUNICORN_WORKERS:-4}

echo "Starting Gunicorn with timeout=${GUNICORN_TIMEOUT}s and workers=${GUNICORN_WORKERS}..."
exec gunicorn --workers=${GUNICORN_WORKERS} --bind=0.0.0.0:5000 --timeout=${GUNICORN_TIMEOUT} "app:create_app()"