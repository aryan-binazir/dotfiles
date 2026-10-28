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
# Linux/macOS; requires Git + Rust/Cargo:
herdr plugin install aryan-binazir/herdr-agents-picker --ref 93ee543f032716d231c83bbd36e46397074f1e67
```

Plugins require registration on **each machine**, separately from config linking:
- `ar.confirm-close`: bundled Bash, Linux/macOS, Herdr 0.9.1+. Link/register before
  loading the config. `prefix+x` opens an 18×4-cell **Close pane** confirmation.
- `ar.last-workspace`: bundled Bash, Linux/macOS. `prefix+Shift+L` toggles the last
  workspace; visit two workspaces after linking to establish history. Mac setup
  is unverified.
- `yxhta.agents-picker`: our Rust fork keeps the upstream ID and `prefix+a`
  binding. See the fork README at the pinned commit for layout and keys.
  Native macOS setup is unverified.

Before migrating, inspect `herdr plugin list` and back up local modifications
outside the managed checkout. GitHub installs replace in place with rollback;
run the pinned install directly. For a local link, first run
`herdr plugin unlink yxhta.agents-picker`. Advance the pin only to a reviewed
commit on the fork's `main`, then reinstall on each machine. The manifest owns
popup sizing; local sizing overrides are unnecessary.

Adding plugins: review code/hooks/platforms. Put local plugins under `plugins/`
and link their permanent paths; pin external installs with `--ref`. Record setup
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

## Pi status integration

Herdr ships and manages the Pi extension. Use its installer; never vendor,
copy between machines, or hand-edit `herdr-agent-state.ts`.

1. Require Herdr 0.9.1 or newer and Pi installed. Herdr 0.9.1 bundles v9.
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
