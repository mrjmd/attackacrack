# The Environment Variables Saga: A Complete History

## Executive Summary

Over the course of several weeks, we've battled with environment variables being cleared on every deployment to DigitalOcean App Platform. This document chronicles every attempt, failure, and lesson learned.

**Current Status**: Environment variables are still being cleared on deployment. The root cause is that our GitHub Actions workflow fetches the current spec (which may already have cleared env vars) instead of using a proper template with encrypted values.

## Complete Timeline

### August 1, 2025 - Initial Production Setup
- Multiple attempts to get basic deployment working
- Environment variables initially in plain text (security risk)
- Realized we couldn't commit secrets to Git

### August 2, 2025 - The GitHub Secrets Attempt
- **11:32 AM**: Commit `b662b83` "moving env secrets to github"
  - Added `${SECRET_KEY}` placeholders to app.yaml
  - Created GitHub repository secrets
  - BUT: Used wrong action (`action-doctl` not `app_action`)
  - Result: App got literal "${SECRET_KEY}" strings

### August 15, 2025 - The Great Unraveling
- **6:28 PM**: Commit `0354f95` "Remove encryption from all environment variables"
  - Removed `type: SECRET` from all variables
  - Still had no values in app.yaml
  - Variables were being cleared on every deploy

### August 16, 2025 - The Manual Fix Era
- **Early morning**: Multiple attempts with manual fixes
- Created `scripts/fix_env_vars.sh` to restore after each deploy
- **11:37 AM**: Latest deployment cleared all but 4 env vars again

## Timeline of Attempts

### Attempt 1: Plain Environment Variables in app.yaml
**Commit**: Initial setup
**Approach**: Declare environment variables with values directly in app.yaml
**Result**: ❌ FAILED - Security risk, secrets exposed in Git
**Lesson**: Never commit secrets to version control

### Attempt 2: Environment Variables with type: SECRET
**Commit**: `490b3b3 secrets cleanup`
**Approach**: Mark environment variables as `type: SECRET` in app.yaml
**Problem**: No values were provided, just the key and type
**Result**: ❌ FAILED - App couldn't read empty encrypted variables
**Lesson**: SECRET type requires actual values to encrypt

### Attempt 3: GitHub Repository Secrets with Placeholders
**Commits**: 
- `b662b83 moving env secrets to github`
- Created `update-image-only.sh` script attempting to use non-existent `doctl apps update-component`
- `e2656c4 switching back to using repo level secrets`
- Removed `type: SECRET` hoping that would help
**Approach**: 
1. Added placeholders in app.yaml: `value: ${SECRET_KEY}`
2. Initially marked them as `type: SECRET`
3. Stored actual values in GitHub repository secrets
4. Expected GitHub/DO to substitute values during deployment
**What Actually Happened**:
```yaml
# In deploy.yml, we used:
- uses: digitalocean/action-doctl@v2  # ← This ONLY installs CLI
  with:
    token: ${{ secrets.DIGITALOCEAN_ACCESS_TOKEN }}

# Then ran:
- run: doctl apps update $APP_ID --spec .do/app-deploy.yaml

# Result: App literally received "${SECRET_KEY}" as the value!
```
**Problem**: The placeholders `${SECRET_KEY}` were NOT being substituted!
- We used `digitalocean/action-doctl` which only installs the CLI tool
- We needed `digitalocean/app_action` which has substitution engine
- The literal string `${SECRET_KEY}` was being deployed as the env var value
- App tried to connect to Redis using the string "${REDIS_URL}"
**Result**: ❌ FAILED - App got literal `${SECRET_KEY}` instead of actual values
**Critical Lesson**: We were using the WRONG GitHub Action!

### Attempt 4: Remove Encryption, Use Plain Text
**Commit**: `0354f95 Remove encryption from all environment variables`
**Approach**: Remove `type: SECRET` from all env vars
**Problem**: Still no values in app.yaml
**Result**: ❌ FAILED - Variables declared without values = cleared on deploy
**Lesson**: Declaring env vars without values tells DO to set them to empty

### Attempt 5: Native DigitalOcean Management
**Commit**: `6a552b2 Fix deployment: Use native DigitalOcean env var management`
**Approach**: Remove env vars from app.yaml entirely, manage through DO dashboard
**Problem**: GitHub Actions deployment uses app.yaml which has no env vars
**Result**: ❌ FAILED - Deployment clears all env vars not in spec
**Lesson**: `doctl apps update --spec` replaces ENTIRE spec

### Attempt 6: Manual Fix Script
**Commit**: `602424f Fix environment variables being cleared on deployment`
**Approach**: Created `scripts/fix_env_vars.sh` to restore env vars after deploy
**Result**: ✅ WORKS but requires manual intervention
**Lesson**: Not a sustainable solution

### Attempt 7: Fetch Current Spec in GitHub Actions
**Commit**: `9f41b83 Fix deployment workflow to preserve environment variables`
**Approach**: Modify deploy.yml to fetch current spec before updating
```yaml
doctl apps spec get ${{ env.APP_ID }} > .do/app-deploy.yaml
sed -i "s/tag: .*/tag: ${{ steps.image-tag.outputs.tag }}/g" .do/app-deploy.yaml
doctl apps update ${{ env.APP_ID }} --spec .do/app-deploy.yaml
```
**Problem**: If previous deployment already cleared env vars, fetching spec gets empty vars
**Result**: ❌ FAILED - Circular dependency problem
**Current Status**: This is where we are now

## Root Cause Analysis

### The REAL Problem We Missed

**We've been using the WRONG GitHub Action all along!**

- **What we used**: `digitalocean/action-doctl@v2` - Just installs the doctl CLI
- **What we needed**: `digitalocean/app_action@v2` - Actually handles env var substitution

The `${VARIABLE_NAME}` placeholders we tried ONLY work with the official app deployment action, NOT with plain `doctl` commands!

### The Fundamental Problem

DigitalOcean's `doctl apps update --spec` command **replaces the entire app specification** AND doesn't do any variable substitution. It takes the spec file literally, including any `${PLACEHOLDER}` strings.

### The Circular Dependency

1. Deployment A runs with incomplete spec → clears env vars
2. We manually fix env vars using our script
3. Deployment B fetches "current" spec to preserve env vars
4. But if Deployment A already ran, the "current" spec has no env vars
5. Deployment B deploys empty env vars
6. Cycle repeats

### Why DigitalOcean Does This

- **Security**: Prevents accidental exposure of secrets in specs
- **Determinism**: Spec file is the single source of truth
- **Auditability**: Every deployment has a complete spec

## Available Solutions

### Solution 1: Official DigitalOcean GitHub Action (RECOMMENDED)
Use `digitalocean/app_action` which supports env var substitution:

```yaml
- name: Deploy the app
  uses: digitalocean/app_action/deploy@v2
  env:
    SECRET_KEY: ${{ secrets.SECRET_KEY }}
    REDIS_URL: ${{ secrets.REDIS_URL }}
    # ... all other secrets
  with:
    token: ${{ secrets.DIGITALOCEAN_ACCESS_TOKEN }}
    app_name: attackacrack-prod
```

**Pros**: 
- Built-in env var substitution
- Officially supported
- Handles encryption automatically

**Cons**: 
- Need to migrate all secrets to GitHub
- Different from current workflow

### Solution 2: Encrypted Values in app.yaml
1. Set all env vars with values in DO dashboard
2. Mark them as type: SECRET
3. Export the spec (values will be encrypted)
4. Store encrypted values in app.yaml
5. Deploy with encrypted spec

```yaml
envs:
  - key: SECRET_KEY
    type: SECRET
    value: EV[1:encryptedValueHere:base64data]  # Safe to commit
    scope: RUN_AND_BUILD_TIME
```

**Pros**: 
- Secrets are encrypted, safe in Git
- Single source of truth
- Works with current workflow

**Cons**: 
- Encrypted values are app-specific
- Need to re-encrypt if app is recreated

### Solution 3: Two-Stage Deployment
1. Deploy app structure (without env vars)
2. Use separate API calls to set env vars
3. Never include env vars in spec updates

**Pros**: 
- Complete separation of concerns
- Env vars never in Git

**Cons**: 
- Complex deployment process
- Not atomic

### Solution 4: Spec Templating with Merge
1. Maintain a template spec in Git (no secrets)
2. On deploy, fetch current spec
3. Merge template with current (preserving env vars)
4. Deploy merged spec

**Pros**: 
- Preserves existing env vars
- Template in Git has no secrets

**Cons**: 
- Complex merge logic needed
- Potential for merge conflicts

## Current State Assessment

### What We Have
- ✅ Environment variables set and working (after manual fix)
- ✅ Deployment workflow that attempts to preserve env vars
- ✅ Manual recovery script (`scripts/fix_env_vars.sh`)
- ❌ Automated deployment that preserves env vars

### What Happens on Deploy
1. GitHub Actions triggers on push to main
2. Workflow installs doctl and authenticates
3. Workflow fetches current spec from DO
4. **PROBLEM**: If last deploy cleared env vars, fetched spec is empty
5. Workflow updates image tag
6. Workflow deploys spec (with empty env vars)
7. All env vars except the 4 in app.yaml are cleared

### The 4 Survivors
These env vars survive because they're in app.yaml with values:
- `FLASK_ENV`: "production"
- `FLASK_APP`: "app.py"
- `DATABASE_URL`: ${db.DATABASE_URL}
- `POSTGRES_URI`: ${db.DATABASE_URL}

## The Solution: What We Need to Do

### Step-by-Step Implementation Plan

#### 1. Add Secrets to GitHub Repository (10 minutes)
Go to GitHub repository → Settings → Secrets and variables → Actions → New repository secret

Add these secrets:
- `SECRET_KEY`
- `REDIS_URL` 
- `CELERY_BROKER_URL`
- `CELERY_RESULT_BACKEND`
- `OPENPHONE_API_KEY`
- `OPENPHONE_WEBHOOK_SIGNING_KEY`
- `OPENPHONE_PHONE_NUMBER`
- `OPENPHONE_PHONE_NUMBER_ID`
- `ENCRYPTION_KEY`
- `GEMINI_API_KEY`
- All other env vars from .env file

#### 2. Update app.yaml with Placeholders (5 minutes)
```yaml
envs:
  - key: SECRET_KEY
    value: ${SECRET_KEY}
    type: SECRET
    scope: RUN_AND_BUILD_TIME
  - key: REDIS_URL
    value: ${REDIS_URL}
    type: SECRET
    scope: RUN_AND_BUILD_TIME
  # ... repeat for all secrets
```

#### 3. Replace Deployment Workflow (10 minutes)
Replace the entire deploy.yml with one using the official action:
```yaml
- name: Deploy to DigitalOcean
  uses: digitalocean/app_action/deploy@v2
  env:
    SECRET_KEY: ${{ secrets.SECRET_KEY }}
    REDIS_URL: ${{ secrets.REDIS_URL }}
    # ... all other secrets
  with:
    token: ${{ secrets.DIGITALOCEAN_ACCESS_TOKEN }}
    app_name: attackacrack-prod
```

#### 4. Test Deployment
1. First run manual fix script to restore current env vars
2. Commit and push the changes
3. Verify env vars persist after deployment

### Why This Will Work

1. **We're using the RIGHT action**: `app_action` has built-in substitution
2. **Proven pattern**: This is DigitalOcean's recommended approach
3. **No more circles**: Env vars in GitHub, substituted during deploy
4. **Security**: Values encrypted as SECRET type in DO

### Alternative If GitHub Secrets Approach Fails

If for some reason the official action doesn't work, we can:
1. Get the current working spec with all env vars
2. Mark sensitive ones as type: SECRET
3. Let DO encrypt them
4. Store the encrypted values in app.yaml (safe because encrypted)
5. Deploy with encrypted spec

## Lessons Learned

1. **DigitalOcean's Design Philosophy**: The spec is meant to be complete and self-contained. Partial updates aren't the intended pattern.

2. **Environment Variable Types**: 
   - `GENERAL`: Plain text, visible in logs
   - `SECRET`: Encrypted at rest, decrypted at runtime
   - Both need VALUES to work

3. **Deployment Methods Matter**: 
   - `doctl apps update --spec`: Replaces entire spec
   - Official GitHub Action: Supports templating and substitution
   - Dashboard updates: Preserve existing config

4. **Secret Management Hierarchy**:
   - GitHub Secrets: For CI/CD only
   - DO App-Level Env Vars: Set via dashboard/API
   - Encrypted Spec Values: Safe in Git, app-specific

5. **The Fetch-Modify-Deploy Pattern**: Fragile when previous deployments fail

## Why We Failed Before and Why It Will Work Now

### What We Tried Before (Failed)
```yaml
# We used action-doctl (just installs CLI)
- uses: digitalocean/action-doctl@v2
  with:
    token: ${{ secrets.DIGITALOCEAN_ACCESS_TOKEN }}

# Then manually ran doctl commands
- run: doctl apps update $APP_ID --spec .do/app.yaml

# app.yaml had placeholders
envs:
  - key: SECRET_KEY
    value: ${SECRET_KEY}  # This stayed as literal "${SECRET_KEY}"
```

### What Will Work Now
```yaml
# Use the ACTUAL deployment action
- uses: digitalocean/app_action/deploy@v2
  env:
    SECRET_KEY: ${{ secrets.SECRET_KEY }}  # Pass the actual values
    REDIS_URL: ${{ secrets.REDIS_URL }}
  with:
    token: ${{ secrets.DIGITALOCEAN_ACCESS_TOKEN }}
    app_name: attackacrack-prod

# The action will:
# 1. Read app.yaml with ${SECRET_KEY} placeholders
# 2. Substitute with values from env
# 3. Deploy the substituted spec
```

### The Critical Difference

1. **action-doctl**: Just installs the CLI tool, no magic
2. **app_action/deploy**: Has built-in substitution engine that processes `${VAR}` placeholders

We were so close! We had the right syntax (`${SECRET_KEY}`) but the wrong tool to process it.

## Conclusion

After weeks of attempts, we've learned that:
1. We were using the wrong GitHub Action all along
2. The `${VARIABLE}` syntax we tried only works with `digitalocean/app_action`
3. Plain `doctl` commands don't do any substitution
4. DigitalOcean App Platform has strong opinions about deployment patterns

Our current approach of fetching and modifying specs is fragile and not the intended pattern.

The sustainable solution is to either:
1. Adopt the official GitHub Action with proper secret management
2. Commit to encrypted secrets in the spec
3. Build a robust merge/validation system

The manual fix script works but isn't sustainable for production deployments.

---

*Document created: January 2025*
*Last updated: Current*
*Status: Problem identified, solution pending implementation*