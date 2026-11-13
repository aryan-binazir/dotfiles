#!/usr/bin/env bash
set -u

[[ ${HERDR_ACTIVE_PANE_ID:-} && ${HERDR_SOCKET_PATH:-} ]] ||
    { printf 'Missing Herdr popup pane or socket context; refusing to close.\n' >&2; exit 1; }
# The popup terminal is discarded on exit, so the cursor stays hidden throughout.
printf '\033[?25l Kill? (y/n) '
IFS= read -r -s -n 1 answer || exit 0
[[ $answer == [yY] ]] || exit 0
error=$("${HERDR_BIN_PATH:-herdr}" pane close "$HERDR_ACTIVE_PANE_ID" 2>&1) && exit 0

printf '\033[2J\033[H'
if [[ $error == *confirmation_required* ]]; then
    printf 'Use workspace\nclose. '
else
    printf 'Close failed.\n'
fi
printf 'Any key.'
IFS= read -r -s -n 1 answer || true
exit 1
