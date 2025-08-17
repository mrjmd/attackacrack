# Attack-a-Crack CRM - Specialized Sub-Agents Directory

This directory contains world-class specialized sub-agents designed to provide deep expertise in specific areas of the codebase and integrated systems.

## 🎯 Agent Directory

### Core Development Agents

#### **tdd-enforcer**
- **Purpose**: Enforces test-driven development practices
- **Triggers**: "implement", "create", "build", "add feature"
- **Expertise**: pytest, fixtures, mocking, coverage analysis
- **Use When**: Starting any new feature or modification

#### **repository-architect**
- **Purpose**: Implements repository pattern and clean architecture
- **Triggers**: "repository", "clean architecture", "database abstraction"
- **Expertise**: Repository pattern, Unit of Work, dependency injection
- **Use When**: Refactoring services to repository pattern

#### **flask-test-specialist**
- **Purpose**: Comprehensive testing for Flask applications
- **Triggers**: "test", "coverage", "mock", "pytest"
- **Expertise**: pytest-flask, fixtures, mocking strategies, coverage improvement
- **Use When**: Writing tests, improving coverage, debugging test failures

#### **python-flask-stack-expert** (Enhanced)
- **Purpose**: Deep Flask architecture with Attack-a-Crack patterns
- **Triggers**: "flask", "sqlalchemy", "blueprint", "service registry"
- **Expertise**: Service registry, SQLAlchemy, Celery, project-specific patterns
- **Use When**: Building Flask features, architectural decisions

#### **devops-pipeline-architect** (Enhanced)
- **Purpose**: DigitalOcean deployment and CI/CD expertise
- **Triggers**: "deploy", "docker", "github actions", "digitalocean"
- **Expertise**: DigitalOcean App Platform, GitHub Actions, Docker optimization
- **Use When**: Deployment issues, infrastructure changes, CI/CD setup

#### **general-purpose** (Enhanced)
- **Purpose**: Comprehensive system knowledge and analysis
- **Triggers**: "research", "analyze", "explore", "architecture decision"
- **Expertise**: Full system understanding, multi-component analysis
- **Use When**: Complex problems, architecture decisions, system-wide analysis

### API Integration Agents

#### **openphone-api-specialist**
- **Purpose**: OpenPhone API integration and webhook handling
- **Triggers**: "OpenPhone", "SMS", "webhook", "phone", "messaging"
- **Expertise**: OpenPhone API v1, webhooks, rate limiting, media handling
- **Use When**: Working with SMS/calls, debugging OpenPhone issues

#### **quickbooks-integration-specialist**
- **Purpose**: QuickBooks Online API and financial sync
- **Triggers**: "QuickBooks", "invoice", "customer sync", "OAuth"
- **Expertise**: QuickBooks API, OAuth 2.0, financial data sync
- **Use When**: Implementing financial features, payment tracking

### System Architecture Agents

#### **celery-tasks-specialist**
- **Purpose**: Background task management and async processing
- **Triggers**: "Celery", "background task", "async", "queue"
- **Expertise**: Celery, Redis/Valkey, task orchestration, monitoring
- **Use When**: Creating background tasks, debugging task failures

#### **database-migration-specialist**
- **Purpose**: Database migrations and schema management
- **Triggers**: "migration", "Alembic", "schema change", "database"
- **Expertise**: Alembic, PostgreSQL, zero-downtime migrations
- **Use When**: Creating migrations, optimizing queries, schema changes

#### **campaign-system-specialist**
- **Purpose**: SMS campaign management and automation
- **Triggers**: "campaign", "A/B test", "SMS marketing", "bulk message"
- **Expertise**: Campaign execution, compliance, response tracking
- **Use When**: Working on campaign features, analytics, compliance

### Meta Agents

#### **claude-code-architect**
- **Purpose**: Optimizing Claude Code configuration and workflows
- **Triggers**: "Claude Code", "sub-agent", "hooks", "memory"
- **Expertise**: Claude Code architecture, MCP tools, agent orchestration
- **Use When**: Creating new agents, optimizing Claude Code setup

#### **todo-manager**
- **Purpose**: Session task tracking with automatic persistence
- **Triggers**: Automatically at session start and task changes
- **Expertise**: Todo persistence, context preservation, recovery
- **Use When**: Starting any multi-step task

## 🚀 Usage Patterns

### Automatic Invocation
These keywords in your prompts will automatically trigger specialized agents:
- "implement" → tdd-enforcer
- "test" → flask-test-specialist
- "repository pattern" → repository-architect
- "OpenPhone" → openphone-api-specialist
- "campaign" → campaign-system-specialist

### Manual Invocation
Use the Task tool to explicitly invoke an agent:
```
Task("description", "Detailed prompt for the agent", "agent-name")
```

### Agent Chaining Examples

#### Feature Implementation Chain
```
1. tdd-enforcer → Write tests first
2. repository-architect → Design data layer
3. flask-test-specialist → Verify coverage
4. openphone-api-specialist → Integrate SMS
```

#### Refactoring Chain
```
1. repository-architect → Design repository
2. database-migration-specialist → Create migration
3. tdd-enforcer → Write repository tests
4. flask-test-specialist → Integration tests
```

## 📊 Agent Selection Matrix

| Task Type | Primary Agent | Supporting Agents |
|-----------|--------------|-------------------|
| New Feature | tdd-enforcer | flask-test-specialist, repository-architect |
| API Integration | openphone-api-specialist | celery-tasks-specialist |
| Database Change | database-migration-specialist | repository-architect |
| Background Jobs | celery-tasks-specialist | campaign-system-specialist |
| Testing | flask-test-specialist | tdd-enforcer |
| Campaign Work | campaign-system-specialist | openphone-api-specialist |
| Architecture | repository-architect | database-migration-specialist |
| Claude Optimization | claude-code-architect | todo-manager |

## 🔧 Creating New Agents

Template for new specialized agents:

```markdown
---
name: your-specialist
description: Clear description of when to use this agent
tools: Read, Write, MultiEdit, Bash, Grep
model: sonnet  # or opus for complex, haiku for simple
---

You are a [domain] specialist for the Attack-a-Crack CRM project.

## YOUR EXPERTISE
- Specific technologies
- Patterns you enforce
- Best practices you follow

## PROJECT-SPECIFIC KNOWLEDGE
- Relevant files and services
- Common patterns in codebase
- Integration points

## WORKFLOWS
Step-by-step processes for common tasks

## COMMON ISSUES & SOLUTIONS
Known problems and their fixes

## TESTING PATTERNS
How to test this domain

## DEBUGGING COMMANDS
Useful commands for troubleshooting
```

## 📈 Agent Performance Metrics

Track agent effectiveness:
- **Invocation Count**: How often each agent is used
- **Success Rate**: Tasks completed without errors
- **Time Saved**: Efficiency improvements
- **Coverage Impact**: Test coverage changes
- **Bug Prevention**: Issues caught by agents

## 🔄 Maintenance

### Regular Updates Needed
- API documentation changes (OpenPhone, QuickBooks)
- New patterns discovered in codebase
- Performance optimizations found
- Common issues encountered

### Version Control
All agents are tracked in Git. When updating:
1. Test changes locally
2. Document what changed
3. Commit with descriptive message
4. Share with team

## 🎓 Learning Path

For new developers, use agents in this order:
1. **tdd-enforcer** - Learn TDD practices
2. **flask-test-specialist** - Master testing
3. **repository-architect** - Understand architecture
4. **openphone-api-specialist** - Learn main integration
5. **celery-tasks-specialist** - Async processing
6. **campaign-system-specialist** - Business logic
7. **database-migration-specialist** - Schema management
8. **claude-code-architect** - Optimize workflow

---

*Last Updated: August 17, 2025*
*Total Agents: 13*
*Combined Expertise: Complete coverage of Attack-a-Crack CRM system*