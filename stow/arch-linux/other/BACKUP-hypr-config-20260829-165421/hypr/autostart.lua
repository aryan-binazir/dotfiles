-- Extra autostart processes.
-- o.launch_on_start("my-service")

-- Ar's desktop startup applications.
o.launch_on_start("ghostty")
o.launch_on_start("helium-browser")
o.launch_on_start("zen-browser")
o.exec_on_start("sleep 5 && omarchy-launch-webapp https://launchpad.37signals.com")
