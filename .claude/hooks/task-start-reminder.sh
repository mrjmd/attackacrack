#!/bin/bash

# Task start reminder hook - prompts for appropriate agent usage
# This hook runs when starting new tasks to remind about agent selection

TASK_DESCRIPTION="$1"

# Check for keywords that should trigger specific agents
if [[ "$TASK_DESCRIPTION" =~ (test|tests|testing|TDD) ]]; then
    echo "🧪 Consider: Use the tdd-enforcer agent to write tests first"
fi

if [[ "$TASK_DESCRIPTION" =~ (repository|repositories|refactor|Phase 2) ]]; then
    echo "🏗️ Consider: Use the repository-architect agent for repository pattern work"
fi

if [[ "$TASK_DESCRIPTION" =~ (campaign|SMS|message|OpenPhone) ]]; then
    echo "📱 Consider: Use the campaign-system-specialist or openphone-api-specialist"
fi

if [[ "$TASK_DESCRIPTION" =~ (deploy|CI|CD|GitHub|production) ]]; then
    echo "🚀 Consider: Use the devops-pipeline-architect agent"
fi

if [[ "$TASK_DESCRIPTION" =~ (database|migration|Alembic|PostgreSQL) ]]; then
    echo "🗄️ Consider: Use the database-migration-specialist agent"
fi

# For any multi-step task
echo "📝 For complex tasks: Use the todo-manager agent to create a task list"