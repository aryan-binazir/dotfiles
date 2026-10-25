#!/usr/bin/env bash
set -eu

: "${HERDR_PANE_ID:?missing pane context}" "${HERDR_SOCKET_PATH:?missing server context}" "${HERDR_PLUGIN_ID:?missing plugin context}"
exec "${HERDR_BIN_PATH:-herdr}" plugin pane open \
    --plugin "$HERDR_PLUGIN_ID" --entrypoint confirm \
    --env "HERDR_ACTIVE_PANE_ID=$HERDR_PANE_ID"
