#!/usr/bin/env bash
# record: called on every workspace.focused event, keeps current/previous ids.
# toggle: focuses the previous workspace; the resulting focus event swaps them.
set -u
state="${HERDR_PLUGIN_STATE_DIR:?}"
cur_file="$state/current"
prev_file="$state/previous"

case "${1:-}" in
  record)
    new="${HERDR_WORKSPACE_ID:?}"
    cur=$(cat "$cur_file" 2>/dev/null || true)
    [ "$new" = "$cur" ] && exit 0
    [ -n "$cur" ] && printf '%s' "$cur" > "$prev_file"
    printf '%s' "$new" > "$cur_file"
    ;;
  toggle)
    prev=$(cat "$prev_file" 2>/dev/null || true)
    [ -n "$prev" ] || exit 0
    exec "${HERDR_BIN_PATH:-herdr}" workspace focus "$prev"
    ;;
  *)
    echo "usage: $0 record|toggle" >&2; exit 2 ;;
esac
