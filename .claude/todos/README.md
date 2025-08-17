# Claude Code Todo Archive System

This directory contains an organized history of development sessions and tasks.

## 📁 Directory Structure

```
.claude/todos/
├── README.md           # This file
├── current.md          # Active session (symlink to latest)
├── archive/            # Historical sessions
│   ├── 2025-01/        # Monthly organization
│   │   ├── session-2025-01-15-0930.md
│   │   ├── session-2025-01-15-1445.md
│   │   └── session-2025-01-16-1000.md
│   └── 2025-02/
│       └── session-2025-02-01-0800.md
└── summary.md          # Rolling summary of completed work
```

## 🔄 How It Works

### New Session
1. Creates new file: `archive/YYYY-MM/session-YYYY-MM-DD-HHMM.md`
2. Updates `current.md` symlink to point to new session
3. Inherits any incomplete tasks from previous session

### During Session
- All updates go to current session file
- Automatic saves after each task change
- Preserves context for recovery

### Session End
- File remains in archive with all context
- Summary of completed items added to `summary.md`
- Next session starts fresh but can reference history

## 📊 Benefits

- **No Bloat**: Each session is a separate file
- **Full History**: Can review any past session
- **Easy Cleanup**: Can delete old months when not needed
- **Quick Access**: `current.md` always points to active session
- **Searchable**: Can grep through archive for past decisions

## 🔍 Useful Commands

```bash
# View current session
cat .claude/todos/current.md

# Find when a feature was implemented
grep -r "feature-name" .claude/todos/archive/

# See this month's sessions
ls .claude/todos/archive/$(date +%Y-%m)/

# Review completed work summary
cat .claude/todos/summary.md
```

## 🗑️ Maintenance

- Keep last 3 months of detailed sessions
- Older months can be compressed or deleted
- `summary.md` preserves key accomplishments
- Git-ignored so doesn't clutter repo

---
*System implemented: August 17, 2025*