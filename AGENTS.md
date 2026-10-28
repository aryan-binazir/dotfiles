# Dotfiles

Shared configs and tools support macOS and Arch Linux/Omarchy. This includes `stow/arch-linux/tmux/.config/tmux/tmux.conf`. Check each script's commands and callers for platform scope; preserve shell-version and BSD/GNU compatibility.

The README's layout and installation instructions are stale. Inspect actual sources and installed symlink targets. `BACKUP-*` directories are snapshots, not active sources. `stow/scripts/` is not a Stow package to install wholesale.

## Changes

- Edit repository sources and preserve installed symlinks. Keep locations unless a move is requested; update links and callers on both machines when moving. Never install links to a temporary worktree.
- Wire new executable callers into the installation; files in `stow/scripts/` are not automatically on PATH. Helpers may resolve beside their source.
- Preserve `shell/gw.bash` as a sourced function so it can change the calling shell's directory.
- For tmux spinner, sound, notifications, daemon lifecycle or click navigation, follow `docs/tmux-agent-attention.md`. Keep optional desktop integrations from breaking core tmux/shell behavior or other terminals.
- For `gb`/`gw` cleanup changes, read `docs/git-branch-cleanup.md`.
- For Neovim, use the separate repo linked in `README.md`.
- Ask before changing user-facing behavior or scope, overwriting configs, or making hard-to-reverse changes. Reload live tmux only when requested, using the existing server and installed config; preserve sessions and runtime settings. If no server exists, report that instead of starting one to claim a reload.

## Verification

For docs-only changes, check referenced paths and the diff; no build or dev server. For scripts, run relevant `tests/` tests and syntax checks. Run tmux tests and smoke checks on private servers, isolated from live sessions. For symlink changes, verify targets and installed command resolution. Report tested OSes and native verification gaps; mocked Mac commands do not prove native notifications, permissions or focus.

## Maintaining these instructions

Prune before adding. Code-golf additions using the shortest unambiguous wording. Prefer existing docs and conditional pointers. Keep only non-obvious repository constraints; omit globals and facts available in code, lint or tests. Keep this file under 700 `o200k_base` tokens.
