-- Learn how to configure Hyprland: https://wiki.hypr.land/Configuring/Start/

-- Omarchy's bootstrap keeps path setup out of this user config.
dofile((os.getenv("OMARCHY_PATH") or "/usr/share/omarchy") .. "/default/hypr/bootstrap.lua")

-- Disable all Omarchy default bindings. Add your own in hypr/bindings.lua.
-- omarchy_default_bindings = false
--
-- Or disable only bindings for Omarchy's preinstalled apps/web apps while
-- keeping core window-manager bindings:
-- omarchy_preinstalled_bindings = false

-- Load Omarchy defaults.
require("default.hypr.omarchy")

-- Put your personal overrides in these files. They're loaded after Omarchy's
-- defaults so package updates can improve the defaults without rewriting your
-- ~/.config/hypr files.
require("hypr.monitors")
require("hypr.input")
require("hypr.bindings")
require("hypr.looknfeel")
require("hypr.autostart")

-- Toggle config flags dynamically.
require("default.hypr.toggles")

-- Add any other personal Hyprland configuration below.
-- o.window("qemu", { workspace = "5" })

-- Ar's application workspace routing. "silent" routes without changing focus.
o.window("^org[.]mozilla[.]Thunderbird$", { workspace = "1" })
o.window("^com[.]mitchellh[.]ghostty$", { workspace = "2" })
o.window("^zen$", { workspace = "3 silent", no_initial_focus = true })
o.window("^(chromium|[Gg]oogle-[Cc]hrome|helium)$", { workspace = "4 silent", no_initial_focus = true })
o.window("^md[.]obsidian[.]Obsidian$", { workspace = "5 silent", no_initial_focus = true })
o.window("^chrome-launchpad[.]37signals[.]com__-Default$", { workspace = "5 silent", no_initial_focus = true })
o.window("^chrome-youtube[.]com__-Default$", { workspace = "6" })
o.window("^steam$", { workspace = "6" })
o.window("^chatgpt$", { workspace = "7" })
o.window("^com[.]anthropic[.]Claude$", { workspace = "8" })
o.window("^chrome-web[.]whatsapp[.]com__-Default$", { workspace = "9" })
o.window("^chrome-app[.]slack[.]com__client-Default$", { workspace = "9" })
o.window("^chrome-x[.]com__-Default$", { workspace = "9" })
