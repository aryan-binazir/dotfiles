-- Extra autostart processes.
-- o.launch_on_start("my-service")

-- 60Hz internal panel in power-saver; see monitors.lua.
o.launch_on_start(os.getenv("HOME") .. "/.local/bin/power-refresh-watch")

-- Ar's desktop startup applications.
o.launch_on_start("ghostty")
