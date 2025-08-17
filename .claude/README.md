# Claude Code Enhanced Configuration for Attack-a-Crack CRM

This directory contains enhanced Claude Code configurations to enforce best practices, TDD, and efficient development workflows.

## 🚀 Quick Start

The enhancements are automatically active. Claude Code will:
1. **Enforce TDD** - Block implementation without tests
2. **Use specialized sub-agents** - Automatically invoke experts for specific tasks
3. **Maintain context** - Preserve project knowledge across sessions
4. **Track progress** - Use TodoWrite for all multi-step tasks

## 📁 Structure

```
.claude/
├── agents/               # Custom sub-agent definitions
│   ├── tdd-enforcer.md      # Enforces test-driven development
│   ├── repository-architect.md  # Repository pattern expert
│   └── flask-test-specialist.md # Testing and coverage expert
├── hooks/                # Automated enforcement scripts
│   └── enforce-tdd.sh       # Blocks code without tests
├── settings.json         # Project configuration and hooks
└── README.md            # This file
```

## 🤖 Available Sub-Agents

### Built-in Agents (from Claude Code)
- `python-flask-stack-expert` - Flask, SQLAlchemy, Celery expertise
- `devops-pipeline-architect` - CI/CD, Docker, cloud deployment
- `deep-research-analyst` - Comprehensive research and analysis

### Custom Project Agents
- `tdd-enforcer` - Enforces test-first development
- `repository-architect` - Clean architecture patterns
- `flask-test-specialist` - Comprehensive testing strategies

## 🎯 Usage Examples

### Starting a New Feature
```
User: Add a new endpoint to fetch contact statistics

Claude will automatically:
1. Invoke tdd-enforcer to write tests first
2. Use python-flask-stack-expert for implementation
3. Ensure service registry pattern is followed
4. Run tests to verify everything works
```

### Refactoring to Repository Pattern
```
User: Refactor ContactService to use repository pattern

Claude will:
1. Use repository-architect to design the repository
2. Invoke tdd-enforcer to write repository tests
3. Implement the repository with clean architecture
4. Migrate service to use the new repository
```

### Improving Test Coverage
```
User: Increase test coverage to 95% for contact_service

Claude will:
1. Use flask-test-specialist to analyze coverage gaps
2. Write comprehensive test cases
3. Mock external dependencies properly
4. Verify coverage meets target
```

## ⚙️ Configuration Details

### Hooks
Hooks run automatically at specific points:
- **PreToolUse**: Before writing/editing files (enforces TDD)
- **PostToolUse**: After file modifications (reminds to run tests)
- **UserPromptSubmit**: When you submit a request (shows TDD reminder)

### Auto-Invocation Patterns
Certain keywords trigger specialized agents:
- "implement", "create", "build" → `tdd-enforcer`
- "repository", "clean architecture" → `repository-architect`
- "test", "coverage", "mock" → `flask-test-specialist`

## 📋 Best Practices Enforced

1. **Test-Driven Development**
   - Tests must exist before implementation
   - Tests must fail initially (Red phase)
   - Minimal implementation to pass tests (Green phase)
   - Refactor only with passing tests

2. **Service Registry Pattern**
   - All services accessed via `current_app.services.get()`
   - No direct service instantiation in routes
   - Dependencies injected, not created

3. **Clean Architecture**
   - Routes handle HTTP only
   - Services contain business logic
   - Repositories handle database access
   - Clear separation of concerns

4. **Testing Standards**
   - 95% coverage target for new code
   - Unit tests mock all dependencies
   - Integration tests use test database
   - Every error condition tested

## 🔧 Customization

### Adding New Sub-Agents
Create a new file in `.claude/agents/`:
```markdown
---
name: your-agent-name
description: When to use this agent
tools: Read, Write, Bash
model: sonnet
---

Your agent instructions here...
```

### Adding New Hooks
Edit `.claude/settings.json`:
```json
{
  "hooks": {
    "YourEvent": [
      {
        "matcher": "pattern",
        "hooks": [
          {
            "type": "command",
            "command": "your-command"
          }
        ]
      }
    ]
  }
}
```

## 📊 Monitoring Effectiveness

Check if the enhancements are working:
1. Try to write code without tests - should be blocked
2. Use phrases like "implement feature" - should invoke tdd-enforcer
3. Check test coverage regularly: `docker-compose exec web pytest --cov`
4. Review git history for TDD compliance

## 🚨 Troubleshooting

### If TDD enforcement is too strict
Temporarily disable by renaming `.claude/hooks/enforce-tdd.sh` to `.claude/hooks/enforce-tdd.sh.disabled`

### If agents aren't being invoked
Check that `.claude/agents/` files have correct YAML frontmatter

### If hooks aren't running
Ensure hook scripts are executable: `chmod +x .claude/hooks/*.sh`

## 📈 Success Metrics

With these enhancements, you should see:
- ✅ 100% of new features have tests written first
- ✅ 95%+ code coverage on new code
- ✅ Consistent use of service registry pattern
- ✅ Clean separation between layers
- ✅ Faster development with fewer bugs
- ✅ Better context preservation across sessions

## 🎓 Learning Resources

- [TDD with Claude Code](https://medium.com/@taitcraigd/tdd-with-claude-code)
- [Claude Code Docs](https://docs.anthropic.com/en/docs/claude-code)
- [Repository Pattern](https://martinfowler.com/eaaCatalog/repository.html)
- [Clean Architecture](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)

---

*Configuration Version: 1.0*
*Last Updated: August 17, 2025*
*Maintained by: Claude Code + Human Collaboration*