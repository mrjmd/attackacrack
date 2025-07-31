#!/bin/bash

# Script to remove secrets from git history
# This is a DESTRUCTIVE operation - make sure you have a backup!

echo "⚠️  WARNING: This will rewrite git history!"
echo "Make sure you have a backup of your repository."
echo ""
read -p "Do you want to continue? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Checking for uncommitted changes..."
if [[ -n $(git status -s) ]]; then
    echo "Stashing uncommitted changes..."
    git stash push -m "Temporary stash for secret removal"
    STASHED=true
else
    STASHED=false
fi

echo ""
echo "Creating backup branch..."
git branch backup-before-secret-removal 2>/dev/null || echo "Backup branch already exists"

echo ""
echo "Removing secrets from git history..."

# Remove openphone.key from all commits
echo "Removing openphone.key..."
git filter-branch --force --index-filter \
    'git rm --cached --ignore-unmatch openphone.key' \
    --prune-empty --tag-name-filter cat -- --all

# Remove client_secret.json from all commits
echo "Removing client_secret.json..."
git filter-branch --force --index-filter \
    'git rm --cached --ignore-unmatch client_secret.json' \
    --prune-empty --tag-name-filter cat -- --all

echo ""
echo "Cleaning up..."

# Remove the original refs backed up by filter-branch
git for-each-ref --format="%(refname)" refs/original/ | xargs -n 1 git update-ref -d

# Clean up the reflog
git reflog expire --expire=now --all

# Force garbage collection
git gc --prune=now --aggressive

echo ""
echo "✅ Secrets removed from git history!"
echo ""
echo "⚠️  IMPORTANT NEXT STEPS:"
echo "1. Review the changes carefully"
echo "2. Force push to remote: git push --force --all"
echo "3. Force push tags: git push --force --tags"
echo "4. All team members must re-clone the repository"
echo "5. Delete the backup branch when satisfied: git branch -D backup-before-secret-removal"
echo ""
echo "The secrets have been removed, but make sure to:"
echo "- Rotate/invalidate the exposed OpenPhone API key"
echo "- Regenerate the Google OAuth client secret"