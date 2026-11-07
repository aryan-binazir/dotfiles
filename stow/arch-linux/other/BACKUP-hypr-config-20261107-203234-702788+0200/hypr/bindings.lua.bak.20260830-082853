-- Keep only your personal keybinding overrides here. Add new bindings or
-- unbind defaults before replacing them.

-- See current bindings and descriptions:
--   omarchy menu keybindings --print

-- To disable every Omarchy default binding, set this in
-- ~/.config/hypr/hyprland.lua before require("default.hypr.omarchy"), then add
-- only the bindings you want below:
--   omarchy_default_bindings = false

-- To disable all preinstalled app/webapp bindings, set:
--   omarchy_preinstalled_bindings = false

-- Add a new binding.
-- o.bind("SUPER + SHIFT + R", "SSH", "alacritty -e ssh your-server")

-- Change an existing binding by unbinding it first, then binding the key again.
-- This example changes SUPER+SPACE from the launcher to the Omarchy root menu.
-- hl.unbind("SUPER + SPACE")
-- o.bind("SUPER + SPACE", "Omarchy menu", "omarchy-menu toggle root")

-- Disable a default binding without replacing it.
-- hl.unbind("SUPER + SHIFT + B")

-- Logitech MX Keys examples:
-- o.bind("SUPER + SHIFT + S", nil, "omarchy-capture-screenshot")
-- o.bind("SUPER + H", nil, "voxtype record toggle")
-- o.bind("SUPER + PERIOD", nil, "omarchy-shell shell toggle omarchy.emojis")

-- Remove unwanted Omarchy web-app shortcuts.
hl.unbind("SUPER + SHIFT + A")
hl.unbind("SUPER + SHIFT + ALT + A")
hl.unbind("SUPER + SHIFT + CTRL + G")

-- Ar's close-window binding. ALT + Q was unbound in the current defaults.
o.bind("ALT + Q", "Close window", hl.dsp.window.close())

-- Ar's workspace navigation and window movement.
local ar_workspace_keys = { "1", "2", "3", "4", "5", "6", "7", "8", "9", "0" }
for index, key in ipairs(ar_workspace_keys) do
  local workspace = tostring(index)
  o.bind("ALT + " .. key, "Switch to workspace " .. workspace, hl.dsp.focus({ workspace = workspace }))
  o.bind(
    "ALT + SHIFT + " .. key,
    "Move window to workspace " .. workspace,
    hl.dsp.window.move({ workspace = workspace })
  )
end

-- Ar's system and application shortcuts.
o.bind("SUPER + SHIFT + CTRL + 4", "Region screenshot to clipboard", "omarchy-capture-screenshot region copy")
o.bind("ALT + RETURN", "Terminal", { omarchy = "terminal" })
o.bind("ALT + F", "File manager", { omarchy = "nautilus" })
o.bind("ALT + SHIFT + F", "File manager (cwd)", { omarchy = "nautilus-cwd" })
o.bind("ALT + B", "Browser", { omarchy = "browser" })
o.bind("ALT + SHIFT + B", "Browser (private)", { omarchy = "browser --private" })
o.bind("ALT + N", "Editor", { omarchy = "editor" })
o.bind("ALT + R", "System monitor", { tui = "btop", focus = true })
o.bind("ALT + D", "Docker", { tui = "lazydocker", focus = true })
o.bind("ALT + O", "Obsidian", { launch = "obsidian", focus = "^md[.]obsidian[.]Obsidian$" })
o.bind("ALT + SHIFT + S", "Suspend", "systemctl suspend")
o.bind("ALT + Y", "YouTube", { webapp = "https://youtube.com/" })
o.bind("ALT + SHIFT + G", "WhatsApp", { webapp = "https://web.whatsapp.com/", focus = true })
o.bind("ALT + X", "X", { webapp = "https://x.com/" })
o.bind("ALT + SHIFT + X", "X Post", { webapp = "https://x.com/compose/post" })
o.bind("ALT + SPACE", "Apps menu", "omarchy-menu toggle apps")

-- Voxtype push-to-talk: hold Super + Alt to record, release either key to transcribe.
-- Hyprland does not reliably emit modifier release events, so stop is handled by voxtype-ptt-watch.
hl.unbind("F9")
hl.unbind("SUPER + META")
for _, key in ipairs({ "ALT_L", "ALT_R" }) do
  o.bind("SUPER + " .. key, "Start dictation (push-to-talk)", "voxtype-ptt-start")
end
for _, key in ipairs({ "Super_L", "Super_R" }) do
  o.bind("ALT + " .. key, "Start dictation (push-to-talk)", "voxtype-ptt-start")
end
