alias acc='claude --permission-mode auto'
alias acco='acc --model claude-opus-5 --effort high'
alias accf='acc --model claude-fable-5 --effort high'
alias accs='acc --model claude-sonnet-5 --effort high'
alias acd='codex --sandbox workspace-write --ask-for-approval on-request -c approvals_reviewer=auto_review -c sandbox_workspace_write.network_access=true'
alias acds='acd --model gpt-5.6-sol -c model_reasoning_effort=high'
alias acdt='acd --model gpt-5.6-terra -c model_reasoning_effort=high'
alias acdl='acd --model gpt-5.6-luna -c model_reasoning_effort=xhigh'
alias acu='cursor-agent --sandbox'
alias lg='lazygit'
alias h='hunk diff origin/main...HEAD'
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
