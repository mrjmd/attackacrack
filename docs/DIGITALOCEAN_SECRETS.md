# DigitalOcean App Platform - Secret Management Guide

## Critical Security Information

### The Problem
DigitalOcean's encrypted environment variables (`EV[1:...]` format) are app-specific and cannot be generated outside of DigitalOcean's infrastructure. This creates a challenge when managing secrets in git repositories.

### The Solution

#### For Git Repository (`.do/app.yaml`)
Use placeholder syntax for sensitive values:
```yaml
- key: OPENPHONE_WEBHOOK_SIGNING_KEY
  scope: RUN_AND_BUILD_TIME
  type: SECRET
  value: ${OPENPHONE_WEBHOOK_SIGNING_KEY}
```

#### For Production Deployment
Use one of these methods to set actual values:

##### Method 1: DigitalOcean Dashboard
1. Go to your app in DigitalOcean dashboard
2. Navigate to Settings → App-Level Environment Variables
3. Add/edit the variable with the actual value
4. DigitalOcean automatically encrypts it

##### Method 2: doctl CLI Script
```bash
# Use the provided script (NOT in git)
./scripts/set_webhook_signing_key.sh
```

##### Method 3: doctl CLI Direct
```bash
# Get app ID
APP_ID=$(doctl apps list --format ID,Name --no-header | grep "attackacrack-prod" | awk '{print $1}')

# Get current spec
doctl apps spec get "$APP_ID" > temp-spec.yaml

# Edit temp-spec.yaml manually to add your secret value
# Then apply:
doctl apps update "$APP_ID" --spec temp-spec.yaml

# Clean up
rm temp-spec.yaml
```

## Security Best Practices

### Never Commit Plain Text Secrets
- ✗ `value: "actual-secret-key-here"`
- ✗ `value: NmkyTExvUVVWa1k5STg5VHFUOEFSSzlIbzZVTGpVOTU=`
- ✓ `value: ${OPENPHONE_WEBHOOK_SIGNING_KEY}`
- ✓ `value: EV[1:encrypted:by:digitalocean]` (only if already encrypted)

### Git Repository Management
1. Use placeholders in `.do/app.yaml` for all secrets
2. Add any scripts containing actual secrets to `.gitignore`
3. Document which secrets need to be set in production

### Production Deployment Workflow
1. Deploy app with placeholder values
2. Set actual secrets through dashboard or CLI
3. DigitalOcean automatically encrypts and restarts app
4. Verify app is running with correct configuration

## Emergency Recovery

### If a Secret is Exposed in Git
1. **Immediately rotate the secret** in the external service
2. Remove the secret from git history:
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .do/app.yaml" \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. Force push to all branches
4. Update the secret in DigitalOcean with new value
5. Notify team members to re-clone repository

### Backup Current Production Secrets
```bash
# Save current spec with encrypted values
APP_ID=$(doctl apps list --format ID,Name --no-header | grep "attackacrack-prod" | awk '{print $1}')
doctl apps spec get "$APP_ID" > production-spec-backup-$(date +%Y%m%d).yaml

# Store this backup securely (NOT in git)
```

## Current Secrets Required

The following environment variables must be set in production:

| Variable | Service | Description |
|----------|---------|-------------|
| `OPENPHONE_WEBHOOK_SIGNING_KEY` | Web, Worker | Webhook signature verification |
| `OPENPHONE_API_KEY` | Web, Worker | OpenPhone API authentication |
| `SECRET_KEY` | Web, Worker | Flask session encryption |
| `ENCRYPTION_KEY` | Web, Worker | Database field encryption |
| `REDIS_URL` | Web, Worker | Redis/Valkey connection (auto-set) |
| `DATABASE_URL` | Web, Worker | PostgreSQL connection (auto-set) |
| `GEMINI_API_KEY` | Web, Worker | Google Gemini API |
| `GOOGLE_CLIENT_ID` | Web, Worker | Google OAuth |
| `GOOGLE_CLIENT_SECRET` | Web, Worker | Google OAuth |
| `PROPERTY_RADAR_API_KEY` | Web, Worker | PropertyRadar integration |
| `QUICKBOOKS_CLIENT_ID` | Web, Worker | QuickBooks OAuth |
| `QUICKBOOKS_CLIENT_SECRET` | Web, Worker | QuickBooks OAuth |
| `SMARTLEAD_API_KEY` | Web, Worker | Smartlead integration |

## Verification

### Check Current Environment Variables
```bash
# List all env vars (values are hidden)
APP_ID=$(doctl apps list --format ID,Name --no-header | grep "attackacrack-prod" | awk '{print $1}')
doctl apps spec get "$APP_ID" | grep -A2 "key:"
```

### Test Webhook Signature
```bash
# After setting the signing key, test webhook endpoint
curl -X POST https://your-app.ondigitalocean.app/webhooks/openphone \
  -H "Content-Type: application/json" \
  -H "X-Openphone-Signature: test-signature" \
  -d '{"test": "data"}'
  
# Should return 401 with invalid signature
# Check logs for proper validation
```

## Important Notes

1. **Encrypted values (`EV[1:...]`) in production specs should NOT be copied to git** unless they're already placeholders
2. **The actual encryption happens on DigitalOcean's side** - you cannot create these encrypted values locally
3. **Always use the dashboard or CLI to set production secrets** - never commit them to git
4. **Regularly audit and rotate secrets** as a security best practice

---

Last Updated: 2025-08-26
Security Contact: DevOps Team