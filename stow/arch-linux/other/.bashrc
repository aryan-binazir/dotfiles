# Omarchy environment (OMARCHY_PATH + PATH), needed even for non-interactive shells
[[ -r /usr/share/omarchy/default/bash/env-bootstrap ]] && source /usr/share/omarchy/default/bash/env-bootstrap

# If not running interactively, don't do anything else (leave this above the rc source)
[[ $- != *i* ]] && return

# All the default Omarchy aliases and functions
# (don't mess with these directly, just overwrite them here!)
source "$OMARCHY_PATH/default/bash/rc"

# Add your own exports, aliases, and functions here.
#
# Load local API keys if present.
[ -f "$HOME/.api_keys" ] && source "$HOME/.api_keys"

# Point interactive shells at the systemd user ssh-agent.
if [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then
  export SSH_AUTH_SOCK="$XDG_RUNTIME_DIR/ssh-agent.socket"
fi

alias vi='nvim'
alias vim='nvim'
alias lg='lazygit'
alias venv='source ~/.venv/bin/activate'
alias acc='claude --permission-mode auto'
alias acco='acc --model claude-opus-5 --effort high'
alias accf='acc --model claude-fable-5 --effort high'
alias accs='acc --model claude-sonnet-5 --effort high'
alias acd='codex --sandbox workspace-write --ask-for-approval on-request -c approvals_reviewer=auto_review -c sandbox_workspace_write.network_access=true'
alias acds='acd --model gpt-5.6-sol -c model_reasoning_effort=high'
alias acdt='acd --model gpt-5.6-terra -c model_reasoning_effort=high'
alias acdl='acd --model gpt-5.6-luna -c model_reasoning_effort=xhigh'
alias acu='cursor-agent --auto-review --sandbox enabled'
alias hu='hunk diff origin/main...HEAD'
alias h='herdr'
alias pie='pi update --all && pi'

# Shared shell function maintained in dotfiles.
source "$HOME/repos/dotfiles/shell/gw.bash"

set -h

export NVM_DIR="$HOME/.config/nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"

export GOPATH="$HOME/go"
export PATH="$GOPATH/bin:$HOME/.local/bin:$PATH"

[[ -r "$HOME/.bash_aliases" ]] && source "$HOME/.bash_aliases"
. "$HOME/.cargo/env"

# Railway CLI
[[ -r "$HOME/.railway/env" ]] && source "$HOME/.railway/env"
