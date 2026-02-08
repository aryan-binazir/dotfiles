# If not running interactively, don't do anything (leave this at the top of this file)
[[ $- != *i* ]] && return

# All the default Omarchy aliases and functions
# (don't mess with these directly, just overwrite them here!)
source ~/.local/share/omarchy/default/bash/rc

# Load local API keys if present
[ -f "$HOME/.api_keys" ] && source "$HOME/.api_keys"

# Add your own exports, aliases, and functions here.
#
# Make an alias for invoking commands you use constantly
# add venv
alias vi='nvim'
alias vim='nvim'
alias lg='lazygit'
alias venv='source ~/.venv/bin/activate'
# alias claude='~/.claude/local/claude'
alias acc='claude --dangerously-skip-permissions'
alias acd='codex --dangerously-bypass-approvals-and-sandbox'
alias aco='opencode'
alias update='sudo pacman -Syu && claude update'
alias updateYay='yay -Syu && claude update'

# Re-enable hashing before loading NVM (fixes "hash: hashing disabled" error)
set -h

export NVM_DIR="$HOME/.config/nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# Go/Wails configuration
export GOPATH="$HOME/go"
export PATH="$GOPATH/bin:$PATH"

export PATH="$HOME/.local/bin:$PATH"
