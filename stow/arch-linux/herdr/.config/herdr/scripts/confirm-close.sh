#!/usr/bin/env bash
set -u

if [[ -z ${HERDR_ACTIVE_PANE_ID:-} || -z ${HERDR_SOCKET_PATH:-} ]]; then
    printf 'Missing Herdr popup pane or socket context; refusing to close.\n' >&2
    exit 1
fi

pane=$HERDR_ACTIVE_PANE_ID
printf 'Close pane %s? [y/N] ' "$pane"
answer=
IFS= read -r -n 1 answer || exit 0
printf '\n'
[[ $answer == y || $answer == Y ]] || exit 0
if "${HERDR_BIN_PATH:-herdr}" pane close "$pane"; then
    exit 0
fi

printf '\nPane was not closed. For a linked worktree group, use workspace close.\nPress any key to dismiss. ' >&2
IFS= read -r -n 1 answer || true
exit 1
