# If not running interactively, don't do anything (leave this at the top of this file)
[[ $- != *i* ]] && return

# All the default Omarchy aliases and functions
# (don't mess with these directly, just overwrite them here!)
source ~/.local/share/omarchy/default/bash/rc

# Add your own exports, aliases, and functions here.
#
# Make an alias for invoking commands you use constantly
# alias p='python'
# add venv
alias vi='nvim'
alias vim='nvim'
alias lg='lazygit'
alias venv='source ~/.venv/bin/activate'
alias claude='~/.claude/local/claude'
alias cc='claude --dangerously-skip-permissions'
alias c='codex --search'
alias cur='cursor-agent'
alias oc='opencode'
alias update='sudo pacman -Syu && claude update && npm install -g @openai/codex@latest'
alias updateYay='yay -Syu && claude update && npm install -g @openai/codex@latest'

# Re-enable hashing before loading NVM (fixes "hash: hashing disabled" error)
set -h

export NVM_DIR="$HOME/.config/nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

alias claude="/home/ar/.claude/local/claude"
