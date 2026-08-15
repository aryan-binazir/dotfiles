-- Startup applications migrated from the pre-Quattro config.
o.launch_on_start("ghostty")
o.launch_on_start("chromium")
o.exec_on_start("sleep 2 && uwsm-app -- omarchy-launch-webapp https://launchpad.37signals.com")
