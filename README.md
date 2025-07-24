# .dotfiles

Configuration files and scripts for my development environment, managed with GNU Stow.

## Structure

- `linux-framework-gnu-stow/` - Stow packages for Linux configs
- `dotconfig/` - Legacy config directory (being migrated)
- `gnome/`, `other/`, `tmux/` - Additional configurations

## Installation

### Prerequisites

```bash
# Install GNU Stow
sudo dnf install stow  # Fedora
sudo apt install stow  # Ubuntu/Debian
```

### Setup

1. Clone this repository:
```bash
git clone <your-repo-url> ~/repos/dotfiles
cd ~/repos/dotfiles/linux-framework-gnu-stow
```

2. Backup existing configs (optional):
```bash
mkdir ~/backup-configs
cp ~/.bashrc ~/.bash_profile ~/.tmux.conf ~/backup-configs/
```

3. Stow packages (choose which ones you need):
```bash
# Shell configurations
stow -t ~ bash tmux

# Window manager and applications  
stow -t ~ sway waybar ghostty kanshi
```

### Available Packages

- **bash** - Shell configuration (`.bashrc`, `.bash_profile`)
- **tmux** - Terminal multiplexer configuration
- **sway** - Wayland window manager config
- **waybar** - Status bar configuration
- **ghostty** - Terminal emulator config
- **kanshi** - Display configuration manager

### Security

- API keys and sensitive data are kept in `~/.api_keys` (not tracked in git)
- See `.gitignore` for full list of excluded sensitive files
- The `.gitconfig` is intentionally kept local and not managed by stow

### Dependencies

- tmux tpm
- pgrep
- fzf
- ripgrep
- sway Window Manager
- neovim
- tmux
- wofi

### Separate Configs

My Neovim config: https://github.com/aryan-binazir/neovim-config

