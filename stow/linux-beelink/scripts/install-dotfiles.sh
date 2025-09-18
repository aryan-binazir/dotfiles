#!/bin/bash
# Install dotfiles using GNU Stow

set -e

STOW_DIR="$HOME/repos/dotfiles/linux-framework-gnu-stow"

if [ ! -d "$STOW_DIR" ]; then
    echo "❌ Dotfiles directory not found: $STOW_DIR"
    exit 1
fi

cd "$STOW_DIR"

echo "🏠 Installing dotfiles with GNU Stow..."

# Check if stow is installed
if ! command -v stow >/dev/null 2>&1; then
    echo "❌ GNU Stow is not installed. Please install it first:"
    echo "   sudo dnf install stow    # Fedora"
    echo "   sudo apt install stow    # Ubuntu/Debian"
    exit 1
fi

# Available packages
PACKAGES=(bash tmux ghostty sway waybar kanshi)

echo "📦 Available packages:"
for pkg in "${PACKAGES[@]}"; do
    if [ -d "$pkg" ]; then
        echo "  ✅ $pkg"
    else
        echo "  ❌ $pkg (not found)"
    fi
done

# Install packages
echo "🔗 Creating symlinks..."
for pkg in "${PACKAGES[@]}"; do
    if [ -d "$pkg" ]; then
        echo "Installing $pkg..."
        stow -t "$HOME" "$pkg"
    fi
done

echo "✅ Dotfiles installation complete!"

echo "🔍 Verifying symlinks:"
for config in ~/.bashrc ~/.bash_profile ~/.tmux.conf ~/.config/ghostty ~/.config/sway ~/.config/waybar ~/.config/kanshi; do
    if [ -L "$config" ]; then
        echo "  ✅ $config -> $(readlink "$config")"
    elif [ -e "$config" ]; then
        echo "  ⚠️  $config (exists but not a symlink)"
    else
        echo "  ❌ $config (not found)"
    fi
done

echo "🔒 Security check:"
if [ -f "$HOME/.api_keys" ]; then
    echo "  ✅ ~/.api_keys exists and is not tracked"
else
    echo "  ⚠️  ~/.api_keys not found - you may need to create it"
fi