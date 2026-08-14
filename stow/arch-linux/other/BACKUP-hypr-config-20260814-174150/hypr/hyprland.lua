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

-- Workspace assignments migrated from the pre-Quattro window rules.
o.window("org[.]mozilla[.]Thunderbird", { workspace = "1" })
o.window("(chrome-kjbdgfilnfhdoflbpgamdcdgpehopbep-Default|chrome-calendar[.]google[.]com__-Default)", { workspace = "1" })
o.window("com[.]mitchellh[.]ghostty", { workspace = "2" })
o.window("chromium", { workspace = "3 silent" })
o.window("(Google-chrome|google-chrome|helium|Helium)", { workspace = "4 silent" })
o.window("obsidian", { workspace = "5 silent" })
o.window("(chrome-ijbgeooaanmapjndajkllhcjbjpmnhhp-Default|chrome-launchpad[.]37signals[.]com__-Default)", { workspace = "5 silent" })
o.window("(chrome-kbkccnkbejohggfkineepggmmnbdekdh-Default|chrome-youtube[.]com__-Default|ai-scheduler|steam|Steam)", { workspace = "6" })
o.window("(chrome-bnppglmjfpalnebkpjnhfflioohnlplp-Default|crx_bnppglmjfpalnebkpjnhfflioohnlplp|t3code|Cursor|cursor)", { workspace = "7" })
o.window("(lm-studio|LM Studio|Chatgpt|chrome-claude[.]ai__-Default|chrome-gemini[.]google[.]com__-Default)", { workspace = "8" })
o.window("(chrome-web[.]whatsapp[.]com__-Default|Slack|slack)", { workspace = "9" })
o.window("(chrome-blgdilankhbcpipclgpdndahbehalgkh-Default|crx_blgdilankhbcpipclgpdndahbehalgkh|chrome-cpdadiipndabhlkmcgbkbllgcjmpjggd-Default|chrome-www[.]icloud[.]com__reminders-Default)", { workspace = "10 silent" })
