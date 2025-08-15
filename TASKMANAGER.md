# OpenPhone SMS CRM - Security & Infrastructure Task Manager

## 🚨 CRITICAL PRIORITY - Security Remediation

### Phase 1: Emergency Security Response (IMMEDIATE - Day 1)
**Goal**: Rotate exposed credentials and secure the repository

#### 1.1 Credential Rotation
- [ ] **CRITICAL**: Rotate OpenPhone API key in OpenPhone dashboard
- [ ] **CRITICAL**: Rotate OpenPhone webhook signing key
- [ ] **CRITICAL**: Rotate Google OAuth credentials (client ID and secret)
- [ ] **CRITICAL**: Rotate Gemini API key in Google Cloud Console
- [ ] **CRITICAL**: Rotate QuickBooks client credentials
- [ ] **CRITICAL**: Rotate Property Radar API key
- [ ] **CRITICAL**: Rotate SmartLead API key
- [ ] **CRITICAL**: Generate new encryption key
- [ ] **CRITICAL**: Rotate Ngrok auth token
- [ ] **CRITICAL**: Update all rotated credentials in GitHub Secrets

#### 1.2 Repository Security
- [ ] Remove `.env` file from git history using BFG Repo-Cleaner or git filter-branch
- [ ] Add `.env` to `.gitignore`
- [ ] Create `.env.example` with placeholder values
- [ ] Audit git history for any other exposed secrets
- [ ] Enable GitHub secret scanning alerts

---

## Phase 2: Environment Variable Management Fix (Day 1-2)
**Goal**: Implement proper secret management without template substitution

### 2.1 GitHub Secrets Validation
**Status**: ✅ All required secrets exist in GitHub repository
- [x] Verified 22 secrets are configured in GitHub
- [ ] Document which secrets are used where
- [ ] Remove duplicate/unused secrets
- [ ] Add missing secrets (if any discovered)

### 2.2 DigitalOcean App Platform Configuration
- [ ] Configure secrets directly in DigitalOcean App Platform UI
  - [ ] Navigate to App Settings > Environment Variables
  - [ ] Add all production secrets as encrypted environment variables
  - [ ] Remove placeholder template syntax from app.yaml
- [ ] Update app.yaml to reference DO environment variables properly
- [ ] Remove `sed` substitution from deployment workflow
- [ ] Test deployment with native DO secret management

### 2.3 Local Development Environment
- [ ] Create development environment setup script
- [ ] Document required environment variables in README
- [ ] Add environment variable validation on app startup
- [ ] Create docker-compose.override.yml for local overrides

---

## Phase 3: Redis/Valkey Connection Fix (Day 2-3)
**Goal**: Fix production Redis connectivity issues

### 3.1 Valkey Service Configuration
**Current Status**: Valkey database exists (db-valkey-nyc3-14182)
- [ ] Get Valkey connection string from DigitalOcean
- [ ] Update Redis URL configuration in app settings
- [ ] Fix SSL certificate verification issues
  - [ ] Configure proper SSL mode for Valkey
  - [ ] Update redis connection factory in config.py
  - [ ] Test SSL connection with debug script
- [ ] Update Celery configuration for Valkey SSL
- [ ] Add Valkey as managed component in app.yaml

### 3.2 Connection Testing
- [ ] Create Valkey connection test script
- [ ] Verify Celery worker connectivity
- [ ] Test Celery Beat scheduler
- [ ] Monitor Redis/Valkey performance metrics

---

## Phase 4: CI/CD Pipeline Improvements (Day 3-4)
**Goal**: Modernize deployment pipeline and add security scanning

### 4.1 GitHub Actions Workflow Updates
- [ ] Remove template substitution logic from deployment workflow
- [ ] Add secret scanning step (using TruffleHog or similar)
- [ ] Add dependency vulnerability scanning (Dependabot)
- [ ] Implement SAST (Static Application Security Testing)
- [ ] Add container image scanning before push
- [ ] Fix deployment workflow to use stable app identification

### 4.2 Deployment Strategy
- [ ] Use DigitalOcean app ID instead of grep for app discovery
- [ ] Implement blue-green deployment strategy
- [ ] Add deployment rollback automation
- [ ] Create deployment notification system
- [ ] Add post-deployment health checks

### 4.3 Environment Management
- [ ] Create staging environment in DigitalOcean
- [ ] Set up staging-specific GitHub secrets
- [ ] Implement promotion pipeline (staging → production)
- [ ] Add environment-specific configuration validation

---

## Phase 5: Infrastructure Optimization (Week 2)
**Goal**: Improve scalability, monitoring, and performance

### 5.1 DigitalOcean App Platform Enhancement
- [ ] Upgrade instance sizes (basic-xs → basic-s minimum)
- [ ] Configure auto-scaling policies
  - [ ] Set min/max instance counts
  - [ ] Configure CPU/memory thresholds
  - [ ] Test scaling behavior
- [ ] Add health check endpoints for all services
- [ ] Configure proper resource limits

### 5.2 Database Optimization
- [ ] Review PostgreSQL configuration
- [ ] Set up database connection pooling
- [ ] Configure automated backups
- [ ] Implement point-in-time recovery
- [ ] Add read replica for reporting (if needed)

### 5.3 Static Assets & CDN
- [ ] Configure DigitalOcean Spaces for static assets
- [ ] Set up CDN for static content delivery
- [ ] Implement asset versioning/cache busting
- [ ] Optimize image delivery

### 5.4 Monitoring & Logging
- [ ] Set up application monitoring (New Relic/Datadog)
- [ ] Configure centralized logging
- [ ] Create alerting rules for critical events
- [ ] Set up uptime monitoring
- [ ] Create performance dashboards

---

## Phase 6: Security Hardening (Week 2-3)
**Goal**: Implement security best practices

### 6.1 Application Security
- [ ] Implement rate limiting
- [ ] Add CORS configuration
- [ ] Configure security headers (CSP, HSTS, etc.)
- [ ] Implement request validation
- [ ] Add API authentication middleware
- [ ] Enable audit logging

### 6.2 Infrastructure Security
- [ ] Configure WAF (Web Application Firewall)
- [ ] Set up DDoS protection
- [ ] Implement IP allowlisting for admin endpoints
- [ ] Configure database encryption at rest
- [ ] Set up VPC for internal services
- [ ] Implement secrets rotation policy

### 6.3 Compliance & Documentation
- [ ] Document security procedures
- [ ] Create incident response plan
- [ ] Implement backup and recovery procedures
- [ ] Create security audit checklist
- [ ] Document data retention policies

---

## Phase 7: Developer Experience (Week 3)
**Goal**: Improve development workflow and documentation

### 7.1 Development Environment
- [ ] Create development container (devcontainer)
- [ ] Add pre-commit hooks for security scanning
- [ ] Implement code formatting automation
- [ ] Add comprehensive linting rules
- [ ] Create local development scripts

### 7.2 Documentation
- [ ] Update README with security best practices
- [ ] Document deployment procedures
- [ ] Create troubleshooting guide
- [ ] Document environment variables
- [ ] Create API documentation
- [ ] Add architecture diagrams

### 7.3 Testing Infrastructure
- [ ] Add integration tests for deployments
- [ ] Create end-to-end test suite
- [ ] Implement performance testing
- [ ] Add security testing automation
- [ ] Create test data management strategy

---

## Progress Tracking

### Completed Tasks
- ✅ GitHub Secrets configured (22 secrets verified)
- ✅ DigitalOcean app exists and is deployed
- ✅ Valkey database provisioned

### Current Blockers
1. **🔴 CRITICAL**: Exposed credentials in git history
2. **🟡 HIGH**: Redis/Valkey SSL connection failures
3. **🟡 HIGH**: Fragile deployment with template substitution
4. **🟠 MEDIUM**: No staging environment

### Success Metrics
- [ ] Zero exposed secrets in repository
- [ ] 100% deployment success rate
- [ ] < 30 second deployment rollback time
- [ ] 99.9% uptime SLA
- [ ] All critical vulnerabilities patched within 24 hours

---

## Quick Reference

### Key Commands
```bash
# Check GitHub secrets
gh secret list

# View DigitalOcean apps
doctl apps list

# Check recent deployments
doctl apps list-deployments 4d1674ef-bfba-4fd3-9a97-943fa02c1f70

# View Valkey database
doctl databases get 8f6abeee-fab4-471b-8f7d-66b16e2b6c3e

# Run deployment
gh workflow run "Manual Deploy to Production"
```

### Important IDs
- **DO App ID**: 4d1674ef-bfba-4fd3-9a97-943fa02c1f70
- **DO Valkey ID**: 8f6abeee-fab4-471b-8f7d-66b16e2b6c3e
- **App Name**: attackacrack-prod
- **Region**: NYC3

### Contact Points
- **App URL**: https://attackacrack-prod-5ce6f.ondigitalocean.app
- **GitHub Repo**: https://github.com/mrjmd/attackacrack

---

*Last Updated: 2025-08-15*
*Priority: CRITICAL - Security incident requiring immediate action*