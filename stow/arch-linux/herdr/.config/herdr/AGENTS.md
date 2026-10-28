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
herdr plugin install aryan-binazir/herdr-agents-picker --ref 7fc8e5149cf45b6b21f82975ce901de48a9addab
```

Plugins require registration on **each machine**, separately from config linking:
- `ar.confirm-close`: bundled Bash, Linux/macOS, Herdr 0.9.1+. Link/register before
  loading the config. `prefix+x` opens an 18×4-cell **Close pane** confirmation.
- `ar.last-workspace`: bundled Bash, Linux/macOS. `prefix+Shift+L` toggles the last
  workspace; visit two workspaces after linking to establish history. Mac setup
  is unverified.
- `yxhta.agents-picker`: our Rust fork, retaining the upstream ID for existing
  bindings. `prefix+a` opens a full-width thread list. Herdr supplies the only
  border and `Agents` title. The manifest versions its **95% × 90%** size.
  `1`–`9`, then `0`, open the first ten visible rows immediately. Scrolling and
  refreshes change those labels. `/` starts search, where digits are text;
  `j/k`, Enter and Esc retain navigation, open and cancel behavior.

Before migrating an existing picker, inspect `herdr plugin list` and preserve
local changes. Uninstall only `yxhta.agents-picker`, then run the pinned fork
install above. Keep local plugin links on permanent checkouts, never worktrees.
After fork updates, advance this pin only to the reviewed commit and reinstall
on each machine. No local manifest sizing override is needed.

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

1. Check `herdr --version`. Herdr 0.9.1 bundles integration v9; newer Herdr
   releases may bundle a newer integration. Back up this machine's
   `~/.pi/agent/extensions/herdr-agent-state.ts` and `~/.pi/agent/settings.json`
   if present. Pi must be installed first.
2. Run `herdr integration install pi`, then `herdr integration status`.
   Require `pi: current (v9)` on Herdr 0.9.1, or the current newer version.
   If Herdr supplies an older version, update Herdr before proceeding.
3. Inspect Pi's global and project settings for a negative extension entry
   matching this machine's `herdr-agent-state.ts`. Remove only that exclusion.
   Keep unrelated settings and other disabled extensions. Pi discovers the
   installed file automatically; a current version alone does not mean enabled.
4. Run `/reload` in existing Pi sessions or restart Pi. Recheck settings after
   reload. Run Pi inside Herdr and verify a turn shows working, then idle/done
   in `herdr agent list` and the picker. Do not claim live verification from
   installer output alone. Use an owned test session, not another agent's pane.

Run installation and enablement separately on each machine; never copy absolute
paths from another environment. Native Mac setup is unverified.
