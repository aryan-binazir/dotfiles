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

-- Restore the personal pre-Quattro overrides that differ from current defaults.
hl.unbind("SUPER + ALT + RETURN")
o.bind("SUPER + ALT + RETURN", "Tmux", [[uwsm-app -- xdg-terminal-exec --dir="$(omarchy-cmd-terminal-cwd)" bash -c "tmux attach || tmux new -s Work"]])

hl.unbind("SUPER + SHIFT + W")
o.bind("SUPER + SHIFT + W", "Typora", { launch = "typora --enable-wayland-ime" })

o.bind("SUPER + SHIFT + CTRL + 4", "Screenshot to clipboard", "omarchy-capture-screenshot region copy")
o.bind("SUPER + Q", "Close window", hl.dsp.window.close())
o.bind("SUPER + Z", "Voice input", "voxtype record toggle")
o.bind("ALT + Z", "Voice input", "voxtype record toggle")
o.bind("ALT + code:52", "Voice input", "voxtype record toggle")

o.bind("ALT + RETURN", "Terminal", { omarchy = "terminal" })
o.bind("ALT + F", "File manager", { omarchy = "nautilus" })
o.bind("ALT + SHIFT + F", "File manager (cwd)", { omarchy = "nautilus-cwd" })
o.bind("ALT + B", "Browser", { omarchy = "browser" })
o.bind("ALT + SHIFT + B", "Browser (private)", { omarchy = "browser --private" })
o.bind("ALT + M", "Music", { omarchy = "spotify" })
o.bind("ALT + N", "Editor", { omarchy = "editor" })
o.bind("ALT + R", "Activity", { tui = "btop" })
o.bind("ALT + D", "Docker", { tui = "lazydocker" })
o.bind("ALT + G", "Gemini", { webapp = "https://gemini.google.com" })
o.bind("ALT + O", "Obsidian", { launch = "obsidian", focus = "^obsidian$" })
o.bind("ALT + SLASH", "Passwords", { omarchy = "1password" })
o.bind("ALT + SHIFT + S", "Suspend", "systemctl suspend")

o.bind("ALT + A", "ChatGPT", { webapp = "https://chatgpt.com" })
o.bind("ALT + SHIFT + A", "Grok", { webapp = "https://grok.com" })
o.bind("ALT + C", "Claude", { webapp = "https://claude.ai" })
o.bind("ALT + Y", "YouTube", { webapp = "https://youtube.com/", focus = true })
o.bind("ALT + SHIFT + G", "WhatsApp", { webapp = "https://web.whatsapp.com/", focus = true })
o.bind("ALT + CTRL + G", "Google Messages", { webapp = "https://messages.google.com/web/conversations", focus = true })
o.bind("ALT + X", "X", { webapp = "https://x.com/" })
o.bind("ALT + SHIFT + X", "X Post", { webapp = "https://x.com/compose/post" })

o.bind("ALT + SPACE", "Apps menu", "omarchy-menu toggle apps")

for workspace = 1, 10 do
  local key = "code:" .. tostring(workspace + 9)
  o.bind("ALT + " .. key, "Switch to workspace " .. workspace, hl.dsp.focus({ workspace = tostring(workspace) }))
  o.bind("ALT + SHIFT + " .. key, "Move window to workspace " .. workspace, hl.dsp.window.move({ workspace = tostring(workspace) }))
end
