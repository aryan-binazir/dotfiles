-- Personal input overrides migrated from the pre-Quattro Hyprland config.
hl.config({
  input = {
    kb_layout = "us",
    kb_options = "compose:caps",
    repeat_rate = 40,
    repeat_delay = 600,
    numlock_by_default = true,
    natural_scroll = true,
    touchpad = {
      natural_scroll = true,
      clickfinger_behavior = true,
      scroll_factor = 0.4,
    },
  },
})

o.window("(Alacritty|kitty|foot)", { scroll_touchpad = 1.5 })
o.window("com[.]mitchellh[.]ghostty", { scroll_touchpad = 0.2 })

hl.gesture({ fingers = 3, direction = "horizontal", action = "workspace" })
