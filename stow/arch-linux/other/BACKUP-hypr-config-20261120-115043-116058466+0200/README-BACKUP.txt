Captured 2026-11-20 11:50:43 SAST (+0200) in Africa/Johannesburg.

Source directories and snapshot layout

/home/ar/.config/hypr -> hypr/
/home/ar/.config/omarchy -> omarchy/
/home/ar/.config/ghostty -> ghostty/
/etc/keyd -> keyd/

This is a copy-only snapshot. The copy preserves permissions, timestamps, and
symlinks. Git keeps symlinks and executable bits. Recreate the empty directory
omarchy/themes/aether after a Git checkout if needed.

To restore, copy the Hyprland, Omarchy, and Ghostty trees to their original
locations. Install keyd with sudo pacman -S --needed keyd. Restore keyd/ into
/etc/keyd with root ownership and preserved permissions, then run sudo keyd check.

Use KEYD-STATE.txt to restore whether keyd and udevmon are active and enabled.
If keyd was active and enabled and udevmon was inactive and disabled, stop and
disable udevmon before enabling and starting keyd. They must never grab the same
keyboard at the same time.

Restoring changes the live system and requires a separate request.
