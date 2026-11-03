# Herdr

Target: `~/.config/herdr/config.toml`, not `~/.herdr`. Edit repo sources; preserve
symlinks. Use the permanent checkout. Inspect destinations; create missing links
only, ask before replacing. Keep parent directories real and runtime state outside Git.

```sh
src="$HOME/repos/dotfiles/stow/arch-linux/herdr/.config/herdr"
mkdir -p "$HOME/.config/herdr/plugins"
ln -s "$src/plugins/confirm-close" "$HOME/.config/herdr/plugins/confirm-close"
herdr plugin link "$HOME/.config/herdr/plugins/confirm-close"
ln -s "$src/config.toml" "$HOME/.config/herdr/config.toml"
# Linux/macOS:
ln -s "$src/plugins/last-workspace" "$HOME/.config/herdr/plugins/last-workspace"
herdr plugin link "$HOME/.config/herdr/plugins/last-workspace"
# Linux/macOS; requires Git + Rust/Cargo. Unpinned by choice: tracks our own main.
herdr plugin install aryan-binazir/herdr-triage
# Requires Node 22.12+:
herdr plugin install jhochenbaum/herdr-hunk-diff --ref ac5eef7cec6a65fbf8f0c9bbd61b4383489beba5
# Requires nvim 0.10+; pair with lua/plugins/herdr-nvim.lua in the nvim config:
herdr plugin install ChmaraX/herdr-nvim --ref 26cd43e38126be8012b59f95fd41ef33574d0d08
```

Plugins require registration on **each machine**, separately from config linking:
- `ar.confirm-close`: bundled Bash, Linux/macOS, Herdr 0.9.1+. Link/register before
  loading the config. `prefix+x` opens an 18×4-cell **Close pane** confirmation.
- `ar.last-workspace`: bundled Bash, Linux/macOS. `prefix+Shift+L` toggles the last
  workspace; visit two workspaces after linking to establish history. Mac setup
  is unverified.
- `ar.triage`: our Rust agent picker with settle/snooze/unread/pin triage.
  `prefix+a` opens it; `prefix+w` jumps to the next blocked, then done/unread
  agent; `prefix+]`/`prefix+\` (core `next_agent`/`previous_agent`) follow its
  order. It owns the Agents view; `[ui.sidebar.agents]` shows its `$triage`
  token. Picker keys and rules: the repo README. Codex threads close and reopen only
  when Codex runs without its shared app-server; the shell rc aliases `codex` to
  `codex --no-daemon` for that. Native macOS setup is unverified.
- `jhochenbaum.hunkdiff`: Node, Linux/macOS. `prefix+Shift+H` opens a hunk review;
  `prefix+Shift+R` sends its comments to the agent. Do not run its `setup-keys`
  action: it writes into this config.
- `chmarax.herdr-nvim`: Rust/Bash, Linux/macOS. `prefix+e` toggles the per-tab nvim
  sidebar; `prefix+Shift+E` picks a file the agent touched.

`ar.triage` replaces `yxhta.agents-picker` (archived): if `herdr plugin list`
shows it, `herdr plugin uninstall yxhta.agents-picker` (`unlink` for a local
link). Update `ar.triage` by rerunning its install; reviewed changes land on
its `main`. The manifest owns popup sizing; local sizing overrides are unnecessary.

Adding plugins: review code/hooks/platforms. Put local plugins under `plugins/`
and link their permanent paths; pin third-party installs with `--ref`. Record setup
here; bind qualified action IDs via `[[keys.command]]`, `type = "plugin_action"`.
Avoid Shift+digit/punctuation conflicts.

The close plugin resolves `scripts/confirm-close.sh` beside its repo source;
no separate helper symlink or PATH entry is needed. Existing helper links may stay.
`prefix+x` asks for `y/Y`; any other key or EOF cancels. Alt+Esc remains immediate.
Close errors stay visible until dismissed; protected linked-worktree group closes
are refused, so use Herdr’s normal workspace-close flow for those. Native Mac
behavior still needs verification.

`prefix+f` runs `stow/scripts/hm` (repo-relative), not a plugin. Link to
`~/.local/bin/hm` if absent; requires PATH, Bash, fzf, jq, compatible find/realpath.

Verify links, `herdr config check`, `herdr plugin list`, and
`herdr plugin action list --plugin <id>`. Reload a running server only when
requested: `herdr server reload-config` / `prefix+q`; smoke-test bindings.
Prefix: Ctrl+B. Docs-only changes: check paths/diff; no live reload.

## Smart Rename

Linux/macOS: require Bun 1.2.23+ on the running server's PATH and Herdr 0.7.5+.
Install Bun with the machine's tool manager. Use `pi` and `/login` to connect
`openai-codex` on each machine; keep authentication outside dotfiles.

```sh
herdr plugin install iurysza/herdr-tab-smart-rename --ref v0.6.6 --yes
herdr integration status
# If Pi integration is missing:
herdr integration install pi
```

Inspect `herdr plugin list`; if `kryptamine/herdr-auto-title` is installed, run
`herdr plugin uninstall <its-listed-id>`. Smart Rename alone manages automatic titles.

Track only `model-selection.json` and `naming-prompt.md` in
`plugins/config/tab-smart-rename/`. The selection uses Pi's Luna model with low
thinking. The prompt requires two Title Case words, at most 16 characters total.
Keep installed code, credentials, logs, and runtime state outside the checkout.

On every machine, create and verify the **directory symlink**, not file copies
or individual file links: model selection is saved by atomic replacement.
Inspect an existing destination and preserve its contents outside dotfiles before
replacing it. Keep the `plugins` and `config` parents real.

```sh
src="$HOME/repos/dotfiles/stow/arch-linux/herdr/.config/herdr"
dst="$HOME/.config/herdr/plugins/config/tab-smart-rename"
mkdir -p "$(dirname "$dst")"
# Once the destination is absent:
ln -s "$src/plugins/config/tab-smart-rename" "$dst"
test -L "$dst" || exit 1
for file in model-selection.json naming-prompt.md; do
  test "$(realpath "$dst/$file")" = "$(realpath "$src/plugins/config/tab-smart-rename/$file")" || exit 1
done
herdr plugin action invoke check-ai --plugin tab-smart-rename
herdr plugin action invoke start --plugin tab-smart-rename
herdr plugin action invoke status --plugin tab-smart-rename
herdr server reload-config
herdr plugin log list --plugin tab-smart-rename --limit 10
```

Require completed action logs with exit code 0, the selected model in `check-ai`,
and a running worker in `status`; dispatch success alone is insufficient.
`check-ai` validates configuration without a model request. Preserve manual names;
avoid `rename-all` and resets. Never stop the Herdr server or its sessions.
Native macOS setup is unverified.

## Pi status integration

Herdr ships and manages the Pi extension. Use its installer; never vendor,
copy between machines, or hand-edit `herdr-agent-state.ts`.

1. Check `herdr --version` and `pi --version`. Require Herdr 0.9.1+ and
   Pi 0.80.4+ for the `agent_settled` event. Herdr 0.9.1 bundles v9.
   Locate Pi's agent directory, normally `~/.pi/agent`, or
   `PI_CODING_AGENT_DIR` when set. Back up its `settings.json` and
   `extensions/herdr-agent-state.ts` outside `extensions/`, so Pi cannot
   auto-load the backup.
2. Run `herdr integration install pi`, then `herdr integration status`.
   Require `pi: current (v9)` on Herdr 0.9.1, or a current version above v9
   on newer Herdr. Installer success alone does not mean enabled.
3. Inspect the agent directory's `settings.json` and project `.pi/settings.json`.
   Remove only an exact `-<path>/herdr-agent-state.ts` exclusion for this
   machine. Preserve other settings and exclusions. If a broader `!pattern`
   excludes it, narrow that pattern while preserving exclusions for other
   files. Pi discovers the installed extension automatically.
4. Run `/reload` in existing Pi sessions or restart Pi. Recheck settings after
   reload. In an owned Pi session inside Herdr, verify a turn shows working,
   then idle/done in `herdr agent list` and the picker. Installer output alone
   is not live verification.

Run installation and enablement separately on each machine; never copy absolute
paths from another environment. Native Mac setup is unverified.
