# Production Deployment Plan
**Attack-a-Crack CRM - Production Strategy & Implementation Guide**

*Last Updated: July 29, 2025*

---

## 🎯 Executive Summary

This document outlines the production deployment strategy for the Attack-a-Crack CRM system, including platform recommendations, security implementation, cost analysis, and step-by-step deployment guide.

**Target Timeline:** 3 weeks to full production deployment  
**Estimated Monthly Cost:** $50-80  
**Recommended Platform:** DigitalOcean App Platform

---

## 🔗 Webhook Strategy

### Current Issue
Ngrok provides unstable URLs that change frequently, requiring manual webhook updates in OpenPhone dashboard.

### Solutions Evaluated

#### Option 1: Automated Ngrok Updates (Development Only)
```bash
# Auto-update script for development
docker-compose exec web python -c "
import requests
import subprocess
import json
import os

# Get current ngrok URL
result = subprocess.run(['curl', '-s', 'http://ngrok:4040/api/tunnels'], 
                       capture_output=True, text=True)
data = json.loads(result.stdout)
public_url = data['tunnels'][0]['public_url']

# Update OpenPhone webhook via API
webhook_url = f'{public_url}/webhook/openphone'
# Call OpenPhone API to update webhook endpoint
"
```

#### Option 2: Development Subdomain
- Use services like serveo.net or localhost.run
- Set up dedicated dev subdomain: `dev-webhooks.attackacrack.com`

#### ✅ Recommended Solution
**Focus on production deployment** - webhook stability issues disappear with permanent domain.

---

## 🏗️ Platform Comparison & Selection

### Platform Options Analysis

| Platform | Monthly Cost | Complexity | Docker Support | Managed Services | Security |
|----------|-------------|------------|----------------|------------------|----------|
| **DigitalOcean App Platform** | $50-80 | Low | Native | PostgreSQL, Redis | High |
| **Railway** | $40-60 | Very Low | Native | PostgreSQL, Redis | Medium |
| **AWS ECS** | $80-150 | High | Native | RDS, ElastiCache | Very High |
| **DigitalOcean Droplet** | $35 | Medium | Manual | Add-on pricing | Medium |
| **Heroku** | $100+ | Low | Good | Expensive add-ons | High |

### 🎯 Recommended: DigitalOcean App Platform

**Why Perfect for Attack-a-Crack CRM:**

✅ **Docker-Native Deployment**
- Direct docker-compose.yml support
- No container registry management
- Automatic builds from Git

✅ **Managed Infrastructure** 
- PostgreSQL database with automatic backups
- Redis instance for Celery/caching
- Load balancing and auto-scaling
- SSL certificates (Let's Encrypt)

✅ **Cost-Effective Scaling**
- Start small, scale automatically
- Pay-per-use pricing model
- No upfront infrastructure costs

✅ **Security & Compliance**
- DDoS protection included
- VPC networking
- SOC 2 Type II compliant
- Automatic security updates

✅ **Developer Experience**
- Git-based deployments
- Real-time logs and monitoring
- Easy rollbacks
- Environment variable management

**Detailed Pricing Breakdown:**
```
Web Application (1GB RAM, 1 vCPU):     $12/month
Celery Worker (512MB RAM, 0.5 vCPU):   $6/month
Celery Beat Scheduler (256MB):          $3/month
PostgreSQL Database (1GB):             $15/month
Redis Cache (256MB):                   $15/month
Bandwidth (moderate usage):             $5-10/month
───────────────────────────────────────────────────
Total Monthly Cost:                    $56-71/month
```

### 🥈 Alternative: Railway

**Pros:**
- Extremely simple deployment
- Great developer experience
- Lower initial cost ($40-60/month)
- Excellent Docker support

**Cons:**
- Newer platform (less proven at scale)
- Fewer enterprise features
- Limited customization options

### 🥉 Budget Option: DigitalOcean Droplet

**Pros:**
- Full control over environment
- Lower base cost ($20/month for 4GB droplet)
- Can customize everything

**Cons:**
- Manual server management required
- No managed database (add $15/month)
- Manual security updates
- No automatic scaling
- More DevOps overhead

---

## 🔐 Security Implementation Strategy

### Phase 1: Immediate Protection (Launch Week)

#### Basic Authentication Layer
```nginx
# nginx.conf - Protect entire application
server {
    listen 80;
    server_name app.attackacrack.com;
    
    location / {
        auth_basic "Attack-a-Crack CRM - Authorized Personnel Only";
        auth_basic_user_file /etc/nginx/.htpasswd;
        
        proxy_pass http://web:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    
    # Webhook endpoint bypass (OpenPhone needs direct access)
    location /webhook/openphone {
        proxy_pass http://web:5000;
        # Webhook signature verification handles security
    }
}
```

#### Environment Security
```bash
# Production environment variables
FLASK_ENV=production
SECRET_KEY=generate-strong-random-key-here
DATABASE_URL=postgresql://...  # Managed database URL
REDIS_URL=redis://...          # Managed Redis URL

# OpenPhone API security
OPENPHONE_API_KEY=your-api-key
OPENPHONE_WEBHOOK_SECRET=your-webhook-secret

# Rate limiting
RATE_LIMIT_STORAGE_URL=redis://...
```

### Phase 2: Application-Level Authentication (Month 2)

#### Flask-Login Implementation
```python
# services/auth_service.py
from flask_login import UserMixin, login_user, logout_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'admin', 'user'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)

# routes/auth.py
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        
        if user and check_password_hash(user.password_hash, password):
            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            db.session.commit()
            return redirect(url_for('dashboard.index'))
    
    return render_template('auth/login.html')

# Protect routes
@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')
```

### Phase 3: Role-Based Access Control (Month 3+)

#### Permission System
```python
# decorators/permissions.py
from functools import wraps
from flask_login import current_user

def require_role(role):
    def decorator(f):
        @wraps(f)
        @login_required
        def decorated_function(*args, **kwargs):
            if current_user.role != role and current_user.role != 'admin':
                abort(403)
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Usage
@app.route('/admin/campaigns')
@require_role('admin')
def admin_campaigns():
    return render_template('admin/campaigns.html')
```

---

## 📋 Step-by-Step Deployment Guide

### Week 1: Platform Setup & Initial Deployment

#### Day 1-2: DigitalOcean Configuration

**1. Create DigitalOcean Account & Project**
```bash
# Install doctl CLI
brew install doctl  # macOS
# or download from: https://github.com/digitalocean/doctl

# Authenticate
doctl auth init
doctl account get
```

**2. Create App Specification**
```yaml
# .do/app.yaml
name: attackacrack-crm
region: nyc1

services:
- name: web
  source_dir: /
  github:
    repo: your-username/openphone-sms
    branch: main
    deploy_on_push: true
  
  build_command: |
    pip install -r requirements.txt
  
  run_command: |
    flask db upgrade
    gunicorn --bind 0.0.0.0:8080 --workers 2 --timeout 120 app:app
  
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-s  # 1GB RAM, 1 vCPU
  
  health_check:
    http_path: /health
    initial_delay_seconds: 60
    
  envs:
  - key: FLASK_ENV
    value: production
  - key: DATABASE_URL
    scope: RUN_AND_BUILD_TIME
    value: ${crm-db.DATABASE_URL}
  - key: REDIS_URL  
    scope: RUN_AND_BUILD_TIME
    value: ${crm-redis.DATABASE_URL}

- name: celery-worker
  source_dir: /
  build_command: pip install -r requirements.txt
  run_command: celery -A celery_worker.celery worker --loglevel=info --concurrency=2
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs  # 512MB RAM
  
- name: celery-beat
  source_dir: /
  build_command: pip install -r requirements.txt  
  run_command: celery -A celery_worker.celery beat --loglevel=info
  environment_slug: python
  instance_count: 1
  instance_size_slug: basic-xxs  # 256MB RAM

databases:
- name: crm-db
  engine: PG
  version: "15"
  size: basic
  num_nodes: 1

- name: crm-redis
  engine: REDIS
  version: "7"
  size: basic
  num_nodes: 1

domains:
- domain: app.attackacrack.com
  type: PRIMARY
```

**3. Deploy Application**
```bash
# Create app
doctl apps create --spec .do/app.yaml

# Monitor deployment
doctl apps list
doctl apps get <app-id>
doctl apps logs <app-id> --type=build
```

#### Day 3-4: Domain & SSL Configuration

**1. DNS Setup**
```bash
# Add CNAME record in your DNS provider:
# app.attackacrack.com -> <your-app-url>.ondigitalocean.app

# Update domain in DigitalOcean
doctl apps update <app-id> --spec .do/app.yaml
```

**2. SSL Certificate (Automatic)**
- DigitalOcean automatically provisions Let's Encrypt certificates
- Verify HTTPS is working: `https://app.attackacrack.com`

#### Day 5-7: Environment Variables & Basic Auth

**1. Environment Configuration**
```bash
# Set production environment variables via DigitalOcean dashboard
FLASK_ENV=production
SECRET_KEY=<generate-256-bit-key>
OPENPHONE_API_KEY=<your-api-key>
OPENPHONE_PHONE_NUMBER=<your-number>
OPENPHONE_PHONE_NUMBER_ID=<your-number-id>
OPENPHONE_WEBHOOK_SECRET=<webhook-secret>
GOOGLE_AI_API_KEY=<gemini-api-key>
```

**2. Basic Authentication Setup**
```bash
# Add to app.yaml or configure via nginx
# Temporary protection until user auth is built
```

### Week 2: Security Hardening

#### Day 8-10: Application Security

**1. Webhook Security Enhancement**
```python
# Update webhook handler for production
@webhook_bp.route('/openphone', methods=['POST'])
def handle_openphone_webhook():
    # Verify signature
    signature = request.headers.get('X-OpenPhone-Signature')
    if not verify_webhook_signature(request.data, signature):
        abort(401)
    
    # Rate limiting
    if not check_rate_limit(request.remote_addr):
        abort(429)
    
    # Process webhook
    return process_webhook_event(request.json)
```

**2. Database Security**
```python
# Connection security
DATABASE_URL = os.environ.get('DATABASE_URL')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)

# Connection pooling for production
engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=300
)
```

#### Day 11-14: Monitoring & Alerting

**1. Application Monitoring**
```python
# Sentry integration for error tracking
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration

sentry_sdk.init(
    dsn="your-sentry-dsn",
    integrations=[FlaskIntegration()],
    traces_sample_rate=0.1,
    environment="production"
)
```

**2. Health Checks**
```python
# app.py - Health check endpoint
@app.route('/health')
def health_check():
    try:
        # Check database connection
        db.session.execute('SELECT 1')
        
        # Check Redis connection
        redis_client = Redis.from_url(os.environ.get('REDIS_URL'))
        redis_client.ping()
        
        return {'status': 'healthy', 'timestamp': datetime.utcnow()}
    except Exception as e:
        return {'status': 'unhealthy', 'error': str(e)}, 500
```

### Week 3: Backup, Monitoring & Go-Live

#### Day 15-17: Backup Strategy

**1. Database Backups**
```bash
# DigitalOcean managed database includes:
# - Daily automated backups (retained 7 days)
# - Point-in-time recovery
# - Manual backup triggers

# Additional backup to external storage
doctl databases backup <database-id>
```

**2. Application Data Backup**
```python
# Backup uploaded files and media
# Set up weekly backup job via Celery
@celery.task
def backup_media_files():
    # Backup to DigitalOcean Spaces or AWS S3
    pass
```

#### Day 18-19: Performance Optimization

**1. Database Optimization**
```sql
-- Add indexes for common queries
CREATE INDEX idx_conversations_last_activity ON conversations(last_activity_at DESC);
CREATE INDEX idx_activities_conversation_created ON activities(conversation_id, created_at);
CREATE INDEX idx_contacts_phone ON contacts(phone_number);
```

**2. Caching Strategy**
```python
# Redis caching for expensive operations
from flask_caching import Cache

cache = Cache(app, config={'CACHE_TYPE': 'redis'})

@cache.memoize(timeout=300)
def get_dashboard_stats():
    # Expensive dashboard queries
    pass
```

#### Day 20-21: Go-Live Preparation

**1. Data Migration**
```bash
# Import production data
docker-compose exec web python large_scale_import.py --reset
docker-compose exec web python csv_contact_enrichment.py
```

**2. Final Testing**
```bash
# Test all critical paths
# - Webhook receiving
# - Campaign sending  
# - Data import/export
# - Authentication
```

---

## 🚨 Security Checklist

### Pre-Launch Security Audit

#### ✅ Application Security
- [ ] All routes protected by authentication
- [ ] Webhook signature verification enabled
- [ ] Rate limiting implemented
- [ ] SQL injection prevention (SQLAlchemy parameterized queries)
- [ ] XSS prevention (template escaping enabled)
- [ ] CSRF protection enabled
- [ ] Secure session configuration
- [ ] Environment variables secured

#### ✅ Infrastructure Security  
- [ ] HTTPS/SSL certificate active
- [ ] Database access restricted to application
- [ ] Redis password protected
- [ ] VPC networking configured
- [ ] Firewall rules configured
- [ ] Regular security updates enabled

#### ✅ Data Protection
- [ ] Database backups automated
- [ ] Sensitive data encrypted at rest
- [ ] API keys rotated and secured
- [ ] PII handling compliant
- [ ] Data retention policies defined

---

## 📊 Monitoring & Alerting Strategy

### Key Metrics to Monitor

#### Application Health
- Response time (target: <500ms for 95th percentile)
- Error rate (target: <1%)
- Uptime (target: 99.9%)
- Memory usage
- CPU utilization

#### Business Metrics
- Webhook processing success rate
- Campaign delivery rates
- Contact import success rates
- Database connection pool health
- Celery task queue depth

### Alerting Configuration

#### Critical Alerts (Immediate Response)
- Application down (>2 minute outage)
- Database connection failures
- Webhook processing failures (>10% error rate)
- Disk space >90% full

#### Warning Alerts (Next Business Day)
- Response time >1 second sustained
- Error rate >0.5%
- Failed Celery tasks
- Low webhook signature verification rate

---

## 💰 Cost Optimization

### Initial Deployment (Month 1)
```
DigitalOcean App Platform:           $56/month
Domain registration:                 $12/year
Sentry error monitoring:            $0 (free tier)
───────────────────────────────────────────────
Total Month 1:                     $56/month
```

### Scaling Costs (Month 6)
```
Web app scaling (2x instances):     +$12/month
Database upgrade (2GB):             +$15/month  
Redis upgrade (512MB):              +$15/month
Additional bandwidth:               +$10/month
───────────────────────────────────────────────
Total Month 6:                     $108/month
```

### Cost Optimization Strategies
1. **Database Connection Pooling**: Reduce database resource usage
2. **Redis Caching**: Minimize expensive database queries  
3. **Image Optimization**: Compress uploaded media files
4. **CDN Implementation**: Use DigitalOcean Spaces for static assets
5. **Right-sizing**: Monitor and adjust instance sizes based on usage

---

## 🔄 Maintenance & Updates

### Weekly Tasks
- [ ] Review error logs and alerts
- [ ] Check application performance metrics
- [ ] Verify backup completion
- [ ] Security update review

### Monthly Tasks  
- [ ] Database performance analysis
- [ ] Cost optimization review
- [ ] Security audit
- [ ] Dependency updates
- [ ] Capacity planning review

### Quarterly Tasks
- [ ] Disaster recovery testing
- [ ] Full security penetration test
- [ ] Performance benchmarking
- [ ] Architecture review

---

## 🎯 Success Metrics

### Technical KPIs
- **Uptime**: >99.9%
- **Response Time**: <500ms (95th percentile)
- **Error Rate**: <1%
- **Webhook Processing**: >99% success rate

### Business KPIs  
- **Data Import Success**: >95% of conversations imported
- **Campaign Delivery**: >98% delivery rate
- **User Satisfaction**: Measured via usage patterns
- **Cost Efficiency**: <$2 per 1000 messages processed

---

## 📞 Emergency Procedures

### Incident Response Plan

#### Severity 1: Application Down
1. Check DigitalOcean status page
2. Review application logs via dashboard
3. Restart application if needed
4. Escalate to DigitalOcean support if infrastructure issue

#### Severity 2: Degraded Performance
1. Check resource utilization
2. Review recent deployments
3. Scale resources if needed
4. Implement temporary fixes

#### Severity 3: Feature Issues
1. Document issue
2. Create bug report
3. Implement workaround if possible
4. Schedule fix for next deployment

### Contact Information
- **DigitalOcean Support**: Available 24/7 via ticket system
- **Emergency Contacts**: Define key personnel
- **Escalation Path**: Clear chain of command

---

## 🚀 Go-Live Decision Criteria

### Technical Readiness
- [ ] All security measures implemented
- [ ] Performance testing completed
- [ ] Backup and recovery tested
- [ ] Monitoring and alerting active
- [ ] Emergency procedures documented

### Business Readiness
- [ ] Data migration completed successfully
- [ ] User access configured
- [ ] Training materials prepared
- [ ] Support processes defined
- [ ] Go-live communication sent

### Final Go/No-Go Meeting
- Review all checklist items
- Confirm support availability
- Verify rollback procedures
- Get stakeholder approval
- Execute go-live plan

---

*This production plan is designed to get Attack-a-Crack CRM from development to production-ready in 3 weeks with enterprise-grade security, monitoring, and scalability.*

**Next Steps:**
1. Review and approve this plan
2. Set up DigitalOcean account
3. Configure GitHub repository for deployment
4. Begin Week 1 implementation

---

**Questions or Concerns?**
- Review the platform comparison if considering alternatives
- Consult the security checklist for compliance requirements  
- Reference the cost optimization section for budget planning
- Use the emergency procedures for incident management