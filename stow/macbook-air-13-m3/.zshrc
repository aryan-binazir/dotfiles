alias vi='nvim'
alias vim='nvim'
alias venv='source ~/.venv/bin/activate'

  export NVM_DIR="$HOME/.nvm"
  [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"  # This loads nvm
  [ -s "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm" ] && \. "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm"  # This loads nvm bash_completion
alias update='brew update && brew upgrade && brew upgrade --cask --greedy && npm -g update && claude update'

# Import my API keys
[ -f ~/.api_keys ] && source ~/.api_keys

# Added by LM Studio CLI (lms)
export PATH="$PATH:/Users/aryanbinazir/.lmstudio/bin"
# End of LM Studio CLI section

alias claude="/Users/aryanbinazir/.claude/local/claude"

alias lg=lazygit
export EDITOR=nvim

. "$HOME/.local/bin/env"
