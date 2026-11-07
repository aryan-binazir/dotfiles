-- See https://wiki.hypr.land/Configuring/Basics/Monitors/
-- List current monitors and supported resolutions with: hyprctl monitors all

local omarchy_gdk_scale = 2
local omarchy_monitor_scale = 2

hl.env("GDK_SCALE", tostring(omarchy_gdk_scale))
hl.monitor({ output = "", mode = "preferred", position = "auto", scale = omarchy_monitor_scale })

-- Internal panel: 60Hz in power-saver (~0.4W saved), 120Hz otherwise.
-- ~/.local/bin/power-refresh-watch reloads this on profile change.
local profile_query = io.popen("busctl get-property org.freedesktop.UPower.PowerProfiles /org/freedesktop/UPower/PowerProfiles org.freedesktop.UPower.PowerProfiles ActiveProfile 2>/dev/null")
local power_saver = (profile_query:read("*l") or ""):find("power-saver", 1, true) ~= nil
profile_query:close()
hl.monitor({
  output = "eDP-1",
  mode = power_saver and "2880x1800@60" or "preferred",
  position = "auto",
  scale = omarchy_monitor_scale,
})

-- Configure a specific monitor.
-- hl.monitor({ output = "DP-2", mode = "2560x1440@144", position = "0x0", scale = 1 })

-- Portrait/rotated secondary monitor (transform: 1 = 90°, 3 = 270°).
-- hl.monitor({ output = "DP-2", mode = "preferred", position = "auto", scale = 1, transform = 1 })
