alias acc='claude --permission-mode auto'
alias acd='codex --sandbox workspace-write --ask-for-approval on-request -c approvals_reviewer=auto_review -c sandbox_workspace_write.network_access=true'
alias acu='cursor-agent'
alias lg='lazygit'
alias box='ssh ar@box.local'
alias python= 'python3' 
alias update='brew update && brew upgrade && brew upgrade --cask --greedy && acc update && sync_skills'
alias venv='source ~/.venv/bin/activate'
alias vi=nvim
alias vim=nvim


export PS1='%n %1~ λ '

export EDITOR=nvim
[ -f ~/.api_keys ] && source ~/.api_keys

export PATH="/opt/homebrew/opt/node@22/bin:$PATH"

eval "$(fnm env --use-on-cd --shell zsh)"
export PATH="$HOME/.local/bin:$PATH"
