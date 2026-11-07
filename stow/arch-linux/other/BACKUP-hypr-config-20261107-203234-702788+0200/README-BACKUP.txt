Snapshot: 2026-11-07T20:32:34.702788+02:00
Timezone: UTC+02:00

Resolved sources and destinations:
  /home/ar/.config/hypr     -> hypr/
  /home/ar/.config/omarchy  -> omarchy/
  /home/ar/.config/ghostty  -> ghostty/
  /etc/keyd                -> keyd/

This is a copy-only snapshot, not an active configuration source. Original
files, permissions, symlinks, running services, and existing backups were
left unchanged. Files were copied with cp -a --no-preserve=ownership;
permissions, timestamps, and symlinks are preserved, without following
symlinks or retaining root ownership on the snapshot copies.

All four source trees were readable and checked for obvious credentials
and private keys before copying. None were detected. This is a heuristic
check, not a guarantee that arbitrary configuration content is public.

Voxtype's configuration, personal dictionary, email vocabulary, models,
and binaries are excluded. Omarchy's selected dictation-backend setting
is included as part of its ordinary configuration tree.

RESTORE NOTES -- documentation only; no restore commands were run:

1. Restore hypr/, omarchy/, and ghostty/ to the corresponding original
   user configuration paths above. Review the files before overwriting
   an existing setup and retain their permissions, timestamps, and links.
2. Install keyd with sudo pacman -S --needed keyd. Restore keyd/ into
   /etc/keyd using root privileges, preserving permissions and timestamps
   and setting restored configuration ownership to root. Validate with
   sudo keyd check.
3. Use KEYD-STATE.txt to restore the recorded service states. For this
   snapshot, udevmon was inactive/disabled and keyd was active/enabled.
   Disable and stop udevmon before enabling and starting keyd; both must
   not grab the same keyboard concurrently.
4. Applying these restore steps changes the live system and requires a
   separate user request. Creating this snapshot does not apply them.

Verification: compare each copied tree against its source with
diff -r --no-dereference. All four comparisons must be clean.
