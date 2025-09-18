#!/bin/bash
# Create backup of dotfiles to external location

set -e

DOTFILES_DIR="$HOME/repos/dotfiles"
BACKUP_BASE="$HOME/backup-dotfiles"
TIMESTAMP=$(date '+%Y%m%d_%H%M%S')
BACKUP_DIR="$BACKUP_BASE/$TIMESTAMP"

echo "💾 Creating dotfiles backup..."

# Create backup directory
mkdir -p "$BACKUP_DIR"

# Copy entire dotfiles repo
echo "📁 Copying dotfiles repository..."
cp -r "$DOTFILES_DIR" "$BACKUP_DIR/"

# Create tar archive
echo "📦 Creating compressed archive..."
cd "$BACKUP_BASE"
tar -czf "dotfiles_backup_$TIMESTAMP.tar.gz" "$TIMESTAMP"

# Clean up directory (keep archive)
rm -rf "$TIMESTAMP"

echo "✅ Backup created: $BACKUP_BASE/dotfiles_backup_$TIMESTAMP.tar.gz"

# Keep only last 5 backups
echo "🧹 Cleaning old backups (keeping last 5)..."
ls -t dotfiles_backup_*.tar.gz | tail -n +6 | xargs -r rm

echo "📊 Available backups:"
ls -lh "$BACKUP_BASE"/dotfiles_backup_*.tar.gz 2>/dev/null || echo "No previous backups found"