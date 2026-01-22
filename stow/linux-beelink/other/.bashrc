# If not running interactively, don't do anything (leave this at the top of this file)
[[ $- != *i* ]] && return

# All the default Omarchy aliases and functions
# (don't mess with these directly, just overwrite them here!)
source ~/.local/share/omarchy/default/bash/rc

# Add your own exports, aliases, and functions here.
#
# Make an alias for invoking commands you use constantly
# add venv
alias vi='nvim'
alias vim='nvim'
alias lg='lazygit'
alias venv='source ~/.venv/bin/activate'
# alias claude='~/.claude/local/claude'
alias cc='claude --dangerously-skip-permissions'
# alias c='codex --search'
alias update='sudo pacman -Syu && claude update'
alias updateYay='yay -Syu && claude update'

# Re-enable hashing before loading NVM (fixes "hash: hashing disabled" error)
set -h

export NVM_DIR="$HOME/.config/nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# Added by LM Studio CLI (lms)
export PATH="$PATH:/home/ar/.lmstudio/bin"
# End of LM Studio CLI section

export PATH="$HOME/.local/bin:$PATH"

