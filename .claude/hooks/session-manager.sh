#!/bin/bash
# Session Manager - Handles todo session files intelligently

# Get the project directory
if [[ -z "$CLAUDE_PROJECT_DIR" ]]; then
    CLAUDE_PROJECT_DIR="/Users/matt/Projects/attackacrack/openphone-sms"
fi

CLAUDE_DIR="$CLAUDE_PROJECT_DIR/.claude"
TODOS_DIR="$CLAUDE_DIR/todos"
ARCHIVE_DIR="$TODOS_DIR/archive"
CURRENT_FILE="$TODOS_DIR/current.md"
SUMMARY_FILE="$TODOS_DIR/summary.md"

# Create directories if they don't exist
mkdir -p "$ARCHIVE_DIR"

# Function to start a new session
start_new_session() {
    local timestamp=$(date "+%Y-%m-%d-%H%M")
    local month_dir=$(date "+%Y-%m")
    local session_file="$ARCHIVE_DIR/$month_dir/session-$timestamp.md"
    
    # Create month directory
    mkdir -p "$ARCHIVE_DIR/$month_dir"
    
    # Check if there's a previous session with incomplete tasks
    if [[ -f "$CURRENT_FILE" ]]; then
        # Extract incomplete tasks from previous session
        local pending_tasks=$(grep -A 100 "## 📋 Pending" "$CURRENT_FILE" 2>/dev/null | grep "^- " || echo "")
        local in_progress=$(grep -A 100 "## 🔄 In Progress" "$CURRENT_FILE" 2>/dev/null | grep "^- " || echo "")
    fi
    
    # Create new session file
    cat > "$session_file" << EOF
# Session TODOs - $timestamp
*Started: $(date "+%Y-%m-%d %H:%M:%S")*
*Previous Session: $(readlink "$CURRENT_FILE" 2>/dev/null || echo "First session")*

## 🔄 In Progress
$in_progress

## ✅ Completed This Session

## 📋 Pending
$pending_tasks

## 📝 Session Notes
- Session started at $(date "+%H:%M")

## 🔍 Context for Recovery
### Working On
- Task: Starting new session
- Status: Initialized

### Modified Files This Session

### Commands to Resume
\`\`\`bash
# Add relevant commands here
\`\`\`

---
*Auto-managed by Claude Code session manager*
EOF
    
    # Update current symlink
    ln -sf "$session_file" "$CURRENT_FILE"
    
    echo "📝 New session started: $session_file"
}

# Function to update current session
update_session() {
    if [[ ! -f "$CURRENT_FILE" ]]; then
        start_new_session
    fi
    
    # Add timestamp to last update
    local temp_file="$CURRENT_FILE.tmp"
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    
    # Update the Last Updated line
    sed "s/\*Last Updated:.*/\*Last Updated: $timestamp\*/" "$CURRENT_FILE" > "$temp_file" 2>/dev/null || \
    echo "*Last Updated: $timestamp*" > "$temp_file"
    
    # Only move if sed succeeded
    if [[ -s "$temp_file" ]]; then
        mv "$temp_file" "$CURRENT_FILE"
    fi
}

# Function to close session and update summary
close_session() {
    if [[ ! -f "$CURRENT_FILE" ]]; then
        echo "No active session to close"
        return
    fi
    
    local session_file=$(readlink "$CURRENT_FILE")
    local timestamp=$(date "+%Y-%m-%d %H:%M:%S")
    
    # Extract completed tasks
    local completed=$(grep -A 100 "## ✅ Completed This Session" "$CURRENT_FILE" 2>/dev/null | grep "^- " || echo "")
    
    if [[ -n "$completed" ]]; then
        # Append to summary
        echo -e "\n## Session: $(basename "$session_file" .md)" >> "$SUMMARY_FILE"
        echo "*Completed: $timestamp*" >> "$SUMMARY_FILE"
        echo "$completed" >> "$SUMMARY_FILE"
    fi
    
    # Add session end marker
    echo -e "\n---\n*Session ended: $timestamp*" >> "$CURRENT_FILE"
    
    echo "✅ Session closed: $session_file"
}

# Function to clean old archives
cleanup_old_archives() {
    local months_to_keep=3
    local cutoff_date=$(date -v-${months_to_keep}m "+%Y-%m" 2>/dev/null || date -d "-${months_to_keep} months" "+%Y-%m")
    
    # Find and remove directories older than cutoff
    for dir in "$ARCHIVE_DIR"/*; do
        if [[ -d "$dir" ]]; then
            local dir_name=$(basename "$dir")
            if [[ "$dir_name" < "$cutoff_date" ]]; then
                echo "🗑️  Removing old archive: $dir"
                rm -rf "$dir"
            fi
        fi
    done
}

# Function to get session stats
session_stats() {
    if [[ ! -f "$CURRENT_FILE" ]]; then
        echo "No active session"
        return
    fi
    
    local completed_count=$(grep -c "^- \[" "$CURRENT_FILE" | grep "✅" || echo "0")
    local pending_count=$(grep -A 100 "## 📋 Pending" "$CURRENT_FILE" 2>/dev/null | grep -c "^- " || echo "0")
    local in_progress_count=$(grep -A 100 "## 🔄 In Progress" "$CURRENT_FILE" 2>/dev/null | grep -c "^- " || echo "0")
    
    echo "📊 Session Stats:"
    echo "  ✅ Completed: $completed_count"
    echo "  🔄 In Progress: $in_progress_count"
    echo "  📋 Pending: $pending_count"
}

# Main logic
case "$1" in
    "start")
        start_new_session
        ;;
    "update")
        update_session
        ;;
    "close")
        close_session
        ;;
    "cleanup")
        cleanup_old_archives
        ;;
    "stats")
        session_stats
        ;;
    *)
        # Default: update current session
        update_session
        ;;
esac