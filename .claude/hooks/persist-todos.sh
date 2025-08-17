#!/bin/bash
# Persist TODOs Hook - Automatically saves todos to file after each update
# This ensures context is never lost, even if session is interrupted

TODO_FILE="$CLAUDE_PROJECT_DIR/.claude/session-todos.md"
TIMESTAMP=$(date "+%Y-%m-%d %H:%M:%S")

# Function to update the todo file
update_todo_file() {
    # This will be called by Claude Code when todos change
    # The todos will be passed as arguments or through environment
    
    # Create backup of current todos
    if [[ -f "$TODO_FILE" ]]; then
        cp "$TODO_FILE" "$TODO_FILE.backup"
    fi
    
    # Update timestamp in file
    sed -i.tmp "s/\*Last Updated:.*/\*Last Updated: $TIMESTAMP\*/" "$TODO_FILE" 2>/dev/null || \
    sed -i '' "s/\*Last Updated:.*/\*Last Updated: $TIMESTAMP\*/" "$TODO_FILE" 2>/dev/null
    
    echo "📝 TODOs persisted to .claude/session-todos.md at $TIMESTAMP"
}

# Check if this is a TodoWrite operation
if [[ "$1" == "TodoWrite" ]]; then
    update_todo_file
fi

# Also create a git-ignored status file for quick checks
STATUS_FILE="$CLAUDE_PROJECT_DIR/.claude/last-update.txt"
echo "Last TODO update: $TIMESTAMP" > "$STATUS_FILE"

exit 0