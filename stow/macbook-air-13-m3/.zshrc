  export NVM_DIR="$HOME/.nvm"
  [ -s "/opt/homebrew/opt/nvm/nvm.sh" ] && \. "/opt/homebrew/opt/nvm/nvm.sh"  # This loads nvm
  [ -s "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm" ] && \. "/opt/homebrew/opt/nvm/etc/bash_completion.d/nvm"  # This loads nvm bash_completion

export EDITOR=nvim
# Import my API keys
[ -f ~/.api_keys ] && source ~/.api_keys

# Added by LM Studio CLI (lms)
export PATH="$PATH:/Users/aryanbinazir/.lmstudio/bin"
# End of LM Studio CLI section

alias vi='nvim'
alias vim='nvim'
alias venv='source ~/.venv/bin/activate'
alias lg=lazygit
alias update='brew update && brew upgrade && brew upgrade --cask --greedy && npm -g update && claude update && npm -g update'
alias cc='~/.claude/local/claude --dangerously-skip-permissions'
alias c='codex --search'

# Clean prompt - username directory λ
export PS1='%n %1~ λ '
export EDITOR=nvim
alias edit="nvim"
