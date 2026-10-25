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
# Linux only:
ln -s "$src/plugins/last-workspace" "$HOME/.config/herdr/plugins/last-workspace"
herdr plugin link "$HOME/.config/herdr/plugins/last-workspace"
# Linux/macOS; requires Git + Rust/Cargo:
herdr plugin install yxhta/herdr-agents-picker --ref 5904754d78899ab7bb254eb0717195603c901026
```

Plugins require registration on **each machine**, separately from config linking:
- `ar.confirm-close`: bundled Bash, Linux/macOS, Herdr 0.9.1+. Link/register before
  loading the config. `prefix+x` opens a 48×5-cell **Close pane** confirmation.
- `ar.last-workspace`: bundled Bash, Linux-only. `prefix+Shift+L` toggles the last
  workspace; visit two workspaces after linking to establish history.
- `yxhta.agents-picker`: external Rust. `prefix+a` opens list + preview;
  `j/k`, Enter, `/`, Esc navigate, open, search, cancel. Mac setup is unverified.

Picker size: local **95% × 90%** override. Find its `manifest_path` in
`~/.config/herdr/plugins.json`; set the `picker` pane's width/height there.
Not versioned; updates/reinstalls may reset it.

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
