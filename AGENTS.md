# Repository purpose

Ar uses this repo to keep a similar development setup on macOS and Arch Linux/Omarchy. Shared tmux configuration and command-line tools are linked into each machine's home directory. Shell and desktop settings can differ by OS.

Treat changes to shared configs and scripts as changes for both machines, even when working on Linux. The README's directory and installation instructions are outdated; inspect the actual files and installed links before using them.

## Sources and installation

- The tmux config is `stow/arch-linux/tmux/.config/tmux/tmux.conf`. Its `arch-linux` location does not make it Linux-only.
- `stow/scripts/` contains shared tools alongside Linux-specific utilities. Determine each script's supported platforms from its commands and callers.
- `stow/mac/.zshrc` contains Mac shell settings. Linux shell settings are in `stow/arch-linux/other/.bashrc`, which sources Omarchy's Bash defaults.
- `shell/gw.bash` defines the Bash function that changes the calling shell's directory. An executable cannot replace that behavior.
- Herdr config and plugins live in `stow/arch-linux/herdr/`. Neovim has a separate repo at `~/repos/neovim-config`.
- `BACKUP-*` directories are historical snapshots, not active configuration sources.

The observed Linux wiring is:

| Installed path | Repo source |
| --- | --- |
| `~/.config/tmux/tmux.conf` | `stow/arch-linux/tmux/.config/tmux/tmux.conf` |
| `~/.config/tmux/scripts/{ai-spinner.sh,window-checkout-names.sh,update-branches.sh}` | Corresponding files in `stow/scripts/` |
| Selected commands in `~/.local/bin/` | Files in `stow/scripts/`, sometimes with a different command name |
| `~/.bashrc` | `stow/arch-linux/other/.bashrc` |
| `~/.config/git/ignore` | `stow/arch-linux/other/.config/git/ignore` |
| `~/.config/herdr/config.toml` and `plugins` | Corresponding paths in the Herdr package |

This is a reference for discovery, not an installation manifest. Inspect symlink targets on the current machine and check that they exist. Verify Mac wiring on the Mac before claiming it matches. There is no current repo-wide installer documenting all these links.

Check a package's directory layout and target before running GNU Stow. `stow/scripts/` is a collection of source files, not a home-directory package to install wholesale. The tmux config currently starts Bash and defaults to `canberra-gtk-play` for sound; inspect Mac overrides rather than assuming those defaults suit macOS. Several Python tools use `uv run --script` and declare their Python requirements in the file.

## Changing the setup

1. Inspect Git status and the relevant source, installed link, and callers. Preserve unrelated local edits.
2. Edit the repo source while preserving installed symlinks. Keep existing locations unless a move is requested; a move requires updating links and callers on both machines.
3. For shared code, check shell versions, command availability, and macOS/BSD versus GNU command options. Use OS detection where behavior differs and `$HOME` for home-directory paths.
4. Keep optional desktop integrations from breaking core tmux or shell behavior. Ghostty is the primary terminal, but other terminals must keep working. Notifications are automatic and informational when exact click targeting is unavailable; no manual binding is required.
5. Add installation wiring for new executable callers. Placing a file in `stow/scripts/` alone does not put it on PATH. Some helpers are intentionally resolved beside their source instead of installed separately.
6. Ask before changing user-facing behavior or scope, overwriting existing config files, or making a change that is hard to undo. Reload live tmux only when requested, using the existing server and installed config.

For spinner, sound, notification, daemon lifecycle, or click-navigation changes, read `docs/tmux-agent-attention.md` before editing.

## Verification

Run relevant tests in `tests/` and syntax checks for changed scripts. This repo has no configured project-wide typecheck or lint command. Documentation-only changes require checking referenced paths and the diff; no build or dev server is needed.

The tests use Python's `unittest`. Run the suite with `python3 -m unittest discover -s tests`, or select the relevant test file. Spinner tests use private tmux servers; keep verification isolated from live sessions.

For symlink changes, verify both the target and the installed command's resolution. For shared behavior, report which OS was tested and what remains unverified. Linux tests with mocked macOS commands do not verify native Mac notifications, permissions, or focus behavior. Preserve existing sessions and runtime settings during reloads; if no tmux server exists, report that rather than starting one to claim a reload.
