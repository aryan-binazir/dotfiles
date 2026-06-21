alias acc='claude'
alias accd='claude --dangerously-skip-permissions'
alias acd='codex'
alias acdd='codex --yolo'
alias acu='cursor-agent'
alias acud='cursor-agent --force'
alias aco='opencode'
alias acod='opencode --yolo'
alias lg='lazygit'
alias linuxbox='ssh ar@192.168.86.45'
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
