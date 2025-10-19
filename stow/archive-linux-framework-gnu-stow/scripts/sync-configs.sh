#!/bin/bash
# Sync dotfiles to git repository and push to remote

set -e

DOTFILES_DIR="$HOME/repos/dotfiles"
STOW_DIR="$DOTFILES_DIR/linux-framework-gnu-stow"

cd "$DOTFILES_DIR"

echo "🔄 Syncing dotfiles..."

# Check if there are any changes
if git diff --quiet && git diff --staged --quiet; then
    echo "✅ No changes to sync"
    exit 0
fi

# Show what's being committed
echo "📝 Changes to be committed:"
git status --short

# Add all changes
git add .

# Create commit with timestamp
COMMIT_MSG="Auto-sync dotfiles $(date '+%Y-%m-%d %H:%M:%S')"
git commit -m "$COMMIT_MSG"

# Push to remote
if git remote get-url origin >/dev/null 2>&1; then
    echo "🚀 Pushing to remote..."
    git push origin main
    echo "✅ Dotfiles synced successfully!"
else
    echo "⚠️  No remote configured. Commit created locally."
fi

echo "📊 Recent commits:"
git log --oneline -3