# Herdr

Config lives at `~/.config/herdr/`, not `~/.herdr`. On each machine run `setup.sh`
from `~/repos/dotfiles`; it owns links and plugin pins. Add plugins there after
reviewing their code, hooks and platforms: local ones under `plugins/`, third-party
pinned by commit SHA. Avoid Shift+digit/punctuation keys. macOS is unverified.

- Never run hunk-diff's `setup-keys` action; it writes into `config.toml`.
- Codex threads close and reopen in `ar.triage` only without Codex's shared
  app-server, hence the shell rc alias `codex --no-daemon`.
- Smart Rename: connect `openai-codex` via `pi` then `/login` per machine. Keep
  credentials, logs and runtime state out of the checkout. Preserve manual names;
  avoid `rename-all` and resets.
- Agent integrations: `herdr integration status`, then `herdr integration install
  <agent>` for any not current. Never vendor or edit the installed Pi extension;
  if Pi settings exclude `herdr-agent-state.ts`, remove only that exclusion, then
  `/reload` Pi.

## Verification

Check `herdr config check`, `herdr plugin list` and `herdr plugin action list
--plugin <id>`. Smart Rename: invoke `check-ai`, `start` and `status`, then require
exit 0 in `herdr plugin log list --plugin tab-smart-rename`, the selected model in
`check-ai` and a running worker; dispatch success is insufficient. A Pi turn inside
Herdr must show working, then idle/done in `herdr agent list`. Reload
(`herdr server reload-config`) only when asked; never stop the server.
