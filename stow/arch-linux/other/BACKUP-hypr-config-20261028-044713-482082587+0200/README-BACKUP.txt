Omarchy desktop, terminal, and keyboard-remapper snapshot

Snapshot time: 2026-10-28T04:47:13+02:00 (SAST, UTC+02:00)
Backup skill: cc-config/skills/personal_other/hypr-backup-timestamped/SKILL.md
Skill commit: 09987a4706b375f37782465a49dfa3d8c3d66f36
Dotfiles git pull result: Already up to date.

Resolved sources and destination layout:
/home/ar/.config/hypr    -> hypr/
/home/ar/.config/omarchy -> omarchy/
/home/ar/.config/ghostty -> ghostty/
/etc/keyd               -> keyd/

KEYD-STATE.txt records the installed keyd package version and the LoadState,
ActiveState, and UnitFileState of keyd.service and udevmon.service.

Copy-only policy:
All source trees were copied without changing their contents. Permissions,
timestamps, and symlinks were preserved; symlinks were not followed. Ownership
was not preserved so the snapshot remains owned by the current user. No existing
backup was reused, and no packages or live service/configuration states were
changed by this backup. The initial backup workflow leaves snapshots uncommitted;
committing or pushing requires a separate user request.

Sensitivity review:
The source inventory and Ghostty/keyd files were inspected. No credentials or
private keys were found in the Ghostty/keyd files. Service metadata excludes
logs and environment dumps.

Restore instructions (documentation only; not executed):
Restore hypr/, omarchy/, and ghostty/ to ~/.config/hypr, ~/.config/omarchy, and
~/.config/ghostty respectively, preserving permissions, timestamps, and symlinks.
Review any existing files before overwriting them.

Install the keyboard remapper:
  sudo pacman -S --needed keyd
Restore keyd/ into /etc/keyd with root ownership and the saved permissions.
Validate the restored configuration:
  sudo keyd check

Consult KEYD-STATE.txt before restoring service enablement and running state.
For this snapshot, keyd.service was active/enabled and udevmon.service was
inactive/disabled. Reproduce that setup, after restoring and validating the
configuration, with:
  sudo systemctl disable --now udevmon.service
  sudo systemctl enable --now keyd.service
If udevmon.service is not installed on the destination machine, there is no
udevmon service to disable. Do not run two remappers that grab the same keyboard.

These service and file restore operations change the live system. Perform them
only after a separate user request, not as part of the backup workflow.
