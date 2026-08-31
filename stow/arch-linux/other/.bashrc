# If not running interactively, don't do anything (leave this at the top of this file)
[[ $- != *i* ]] && return

# All the default Omarchy aliases and functions
# (don't mess with these directly, just overwrite them here!)
# /etc/omarchy.conf is written by omarchy-dev-link. When absent, force the
# package default instead of preserving a stale inherited dev-link value before
# we decide which rc file to source.
if [[ -f /etc/omarchy.conf ]]; then
  source /etc/omarchy.conf
  export OMARCHY_PATH="${OMARCHY_PATH:-/usr/share/omarchy}"
else
  export OMARCHY_PATH=/usr/share/omarchy
fi
source "$OMARCHY_PATH/default/bash/rc"

# Load local API keys if present
[ -f "$HOME/.api_keys" ] && source "$HOME/.api_keys"

# Add your own exports, aliases, and functions here.
#
# Point interactive shells at the systemd user ssh-agent.
if [[ -n "${XDG_RUNTIME_DIR:-}" ]]; then
  export SSH_AUTH_SOCK="$XDG_RUNTIME_DIR/ssh-agent.socket"

  # Unlock the GitHub key once per ssh-agent lifetime.
  if ! ssh-add -l >/dev/null 2>&1; then
    ssh-add "$HOME/.ssh/id_ed25519"
  fi
fi

# Make an alias for invoking commands you use constantly
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

# Keep this wrapper in sync with the copyable version in stow/scripts/gw.
gw() {
  if (( $# < 1 )); then
    echo "error: usage: gw <name> [command...]" >&2
    return 1
  fi

  local name="$1"
  shift
  local worktree

  worktree="$(command gw "$name")" || return
  builtin cd "$worktree" || return

  (( $# == 0 )) && return 0
  # Re-eval so shell aliases (acc, acd, acu, acdl, ...) expand.
  eval "$(printf '%q ' "$@")"
}

# Re-enable hashing before loading NVM (fixes "hash: hashing disabled" error)
set -h

export NVM_DIR="$HOME/.config/nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# Go/Wails configuration
export GOPATH="$HOME/go"
export PATH="$GOPATH/bin:$PATH"

export PATH="$HOME/.local/bin:$PATH"

alias box='ssh ar@box.local'
