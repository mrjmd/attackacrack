#!/bin/bash
# Script to restore environment variables after deployment
# This is necessary because the GitHub Actions deployment clears them

echo "Fixing environment variables after deployment..."

# Export all env vars from .env file
export $(grep -v '^#' .env | xargs)

# Create Python script to update spec
cat > /tmp/restore_envs.py << 'PYEOF'
import os
import subprocess
import yaml

# Get app ID
APP_ID = "4d1674ef-bfba-4fd3-9a97-943fa02c1f70"

# Get current spec
result = subprocess.run(['doctl', 'apps', 'spec', 'get', APP_ID], 
                       capture_output=True, text=True)

spec = yaml.safe_load(result.stdout)

# Environment variables to restore
env_vars = {
    'SECRET_KEY': os.environ.get('SECRET_KEY'),
    'REDIS_URL': os.environ.get('REDIS_URL'),
    'CELERY_BROKER_URL': os.environ.get('CELERY_BROKER_URL'),
    'CELERY_RESULT_BACKEND': os.environ.get('CELERY_RESULT_BACKEND'),
    'OPENPHONE_API_KEY': os.environ.get('OPENPHONE_API_KEY'),
    'OPENPHONE_WEBHOOK_SIGNING_KEY': os.environ.get('OPENPHONE_WEBHOOK_SIGNING_KEY'),
    'OPENPHONE_PHONE_NUMBER': os.environ.get('OPENPHONE_PHONE_NUMBER'),
    'OPENPHONE_PHONE_NUMBER_ID': os.environ.get('OPENPHONE_PHONE_NUMBER_ID'),
    'ENCRYPTION_KEY': os.environ.get('ENCRYPTION_KEY'),
    'GEMINI_API_KEY': os.environ.get('GEMINI_API_KEY'),
    'GOOGLE_CLIENT_ID': os.environ.get('GOOGLE_CLIENT_ID'),
    'GOOGLE_CLIENT_SECRET': os.environ.get('GOOGLE_CLIENT_SECRET'),
    'GOOGLE_PROJECT_ID': os.environ.get('GOOGLE_PROJECT_ID'),
    'PROPERTY_RADAR_API_KEY': os.environ.get('PROPERTY_RADAR_API_KEY'),
    'QUICKBOOKS_CLIENT_ID': os.environ.get('QUICKBOOKS_CLIENT_ID'),
    'QUICKBOOKS_CLIENT_SECRET': os.environ.get('QUICKBOOKS_CLIENT_SECRET'),
    'QUICKBOOKS_REDIRECT_URI': os.environ.get('QUICKBOOKS_REDIRECT_URI'),
    'QUICKBOOKS_SANDBOX': os.environ.get('QUICKBOOKS_SANDBOX'),
    'SMARTLEAD_API_KEY': os.environ.get('SMARTLEAD_API_KEY'),
}

updated = 0

# Update services
for service in spec.get('services', []):
    for env in service.get('envs', []):
        if env['key'] in env_vars and env_vars[env['key']]:
            env['value'] = env_vars[env['key']]
            updated += 1
            print(f"Setting {env['key']} for {service.get('name')}")

# Update workers  
for worker in spec.get('workers', []):
    for env in worker.get('envs', []):
        if env['key'] in env_vars and env_vars[env['key']]:
            env['value'] = env_vars[env['key']]
            updated += 1
            print(f"Setting {env['key']} for {worker.get('name')}")

print(f"\nTotal updated: {updated}")

# Save
with open('/tmp/fixed_env_spec.yaml', 'w') as f:
    yaml.dump(spec, f, default_flow_style=False, sort_keys=False)

print("Spec saved to /tmp/fixed_env_spec.yaml")
PYEOF

# Run the Python script
python3 /tmp/restore_envs.py

# Apply the updated spec
echo ""
echo "Applying updated spec to DigitalOcean..."
doctl apps update 4d1674ef-bfba-4fd3-9a97-943fa02c1f70 --spec /tmp/fixed_env_spec.yaml --wait

echo ""
echo "✅ Environment variables restored successfully!"
echo ""
echo "To verify, check the worker logs:"
echo "doctl apps logs 4d1674ef-bfba-4fd3-9a97-943fa02c1f70 attackacrack-worker --tail=20"