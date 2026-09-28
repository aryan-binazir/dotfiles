# Source from ~/.bashrc; external scripts cannot change the parent shell's cwd.
gw() {
  if (( $# < 1 )); then
    echo "error: usage: gw <name> [command...] | gw list | gw rm <name> | gw rm --all [--force]" >&2
    return 1
  fi

  case "$1" in
    list|rm) command gw "$@"; return $? ;;
  esac

  local name="$1"
  shift
  local worktree

  worktree="$(command gw "$name")" || return
  builtin cd "$worktree" || return

  (( $# == 0 )) && return 0
  # Re-eval so shell aliases expand.
  eval "$(printf '%q ' "$@")"
}
