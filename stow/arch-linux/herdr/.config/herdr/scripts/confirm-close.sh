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
if error=$("${HERDR_BIN_PATH:-herdr}" pane close "$pane" 2>&1); then
    exit 0
fi

printf '\033[2J\033[H'
if [[ $error == *confirmation_required* ]]; then
    printf 'Worktree group protected.\nUse workspace close instead.\n'
else
    printf 'Close failed.\n'
fi
printf 'Press any key to dismiss. '
IFS= read -r -n 1 answer || true
exit 1
