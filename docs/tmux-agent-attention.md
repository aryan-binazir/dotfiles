# Agent attention in tmux

`stow/scripts/ai-spinner.sh` keeps the existing spinner and adds unread attention:

- **Spinner:** an agent looks busy, using the existing Claude title and Codex,
  Cursor, and Pi terminal-text heuristics.
- **✓:** an observed busy agent stopped looking busy for three quiet
  observations (roughly two seconds from the first quiet observation).
  Its turn looks stopped, or it is showing a prompt the detector missed, and the
  output is unread. This does not prove task success;
  interrupted turns and errors can also stop activity.
- **!:** a known visible approval or question dialog needs input. This takes
  priority over activity in that pane, including Pi dialogs that retain a spinner.
- Indicators combine when different panes/windows are blocked, stopped, or working.

Window tabs, `prefix s` session and expanded window rows, and `prefix w` use the
same indicators. Expanded pane rows distinguish the individual agents too.
`prefix w` opens with windows collapsed. `prefix W` opens with every session and
window expanded, showing individual panes.
Inside either picker, `Alt` + `+` expands all items and `Alt` + `-` collapses them.
Stable option values refer to a shared hidden environment
variable for the animation frame; consumers expand them with `#{E:@ai_spinner}`
or `#{E:@ai_spinner_s}`. Frame updates use status-only refreshes, not option writes
that invalidate ordinary application panes. Stable idle and unread indicators do
not force repeated redraws. State/indicator transitions can still trigger tmux's
normal full redraw. A session retains its markers while any of its windows has
unread attention; visiting a different window in that session doesn't clear it.

Detection runs roughly once a second and animation roughly four times a second.
Pane state and client metadata are read in bulk, and captured text is filtered in
one pass. Without terminal clients, detection and notifications continue but
animation stops. The internal frame is not exported to new pane processes.

## Acknowledgement and persistence

Both unread indicators clear when that window is shown in a focused attached tmux client,
provided its active pane is not in a picker or copy mode. A foreground completion
still makes a sound but is immediately considered seen. If multiple clients are
attached, viewing the window in any focused client acknowledges it. This is
window-level acknowledgement, not a guarantee that every split was read.
Zooming a pane still acknowledges the entire window. A seen input prompt stays
acknowledged while it remains open; polling and monitor reloads do not alert again.
When the agent resumes, a later prompt or completion can create new attention.

Starting work again supersedes that pane's previous check. Closing the pane
removes its state without creating another completion. Linked windows contribute
to each containing session, but their panes are processed only once per scan.

Unread state is stored in pane-local tmux options, so it survives **config reloads
and daemon restarts while the tmux server lives**. Reloading doesn't replay
already-issued notifications. On Linux, `flock` (util-linux) serializes daemon
handover so an in-flight completion cannot race a replacement. If the `flock`
executable is unavailable, Python 3 takes the lock and replaces itself with the
daemon, retaining its PID and lock descriptor. Scanner, sound, and notification
children do not hold that lock. A replacement prepares its scan directory and
checks lock support before requesting handover; a failed preparation leaves the
running monitor in place. Its empty `<socket>.ai-spinner.lock` file is
intentionally retained to keep concurrent waiters on the same inode. A pane's
window membership is checked inside tmux when persisting a transition, so moving
it mid-scan cannot acknowledge its old window. Aggregation can lag until the next
scan. Destroying/restarting the tmux server does not preserve attention.

This is heuristic monitoring, not lifecycle hooks. Very short work between scans
can be missed; changing an agent's UI wording can break detection. An unrecognized
idle agent does not get marked done just because the monitor starts. Failed
captures don't advance completion detection.

Input detection uses the most recent 20 nonempty screen lines. Claude requires
paired dialog controls, such as confirmation plus cancellation, permission choices,
or MCP input controls. Codex uses its approval/question footer or its `Action Required`
title, including when its npm launcher appears as `node`. Pi uses the standard extension selector/input hints, the installed
auto-permissions selector and note controls, and the questionnaire's controls.
A `π - ` title identifies Pi even behind a shell wrapper.
Ordinary prose mentioning permission or questions does not establish a blocker.
A later Claude/Codex composer, including typed input, makes earlier dialog controls stale. New or
custom dialog layouts and non-visible prompts may still fall back to `✓` after
activity stops. An unanswered question written as ordinary assistant prose is not
classified as a blocking dialog.

A disappearing input dialog uses the same three-observation debounce. A single
redraw does not produce another notification for the same prompt. If work resumes,
the spinner replaces it; if the turn settles, unread output becomes `✓`.

## Desktop notifications

Each newly quiet background pane can show an OS notification saying **Agent turn
finished**. A newly blocked background pane says **Agent needs input**. Both are
labeled with the window and pane indices, such as `W 1 P 2`. The existing
window-level acknowledgement rule suppresses popups for windows you are already
viewing. Popups do not add another sound. Simultaneous panes notify separately;
their existing sound stays coalesced. Dismissing a popup does not clear its marker.

Notifications are automatic. There is no binding shortcut or terminal-title
rewrite. The optional `stow/scripts/tmux-agent-notify` helper uses Python 3's
standard library. It resolves beside the spinner's real source, including when
the installed spinner is a Stow symlink. Missing Python on Linux, a missing helper,
failed notification commands, and unsupported platforms leave existing monitoring
and sound behavior intact. Immediate OS commands have a five-second timeout. Ghostty tty lookup and
`terminal-notifier` delivery can wait for macOS permission dialogs in their
background worker without blocking the monitor or holding its handover lock.
After tty lookup, the worker rechecks the completion and popup mute before
delivery; resumed or acknowledged work and superseded events are suppressed.

| Platform | Delivery | Click navigation |
| --- | --- | --- |
| Linux | `notify-send`, including from non-Ghostty terminals | Informational only. Ghostty 1.3.1 does not provide reliable external window/tab targeting. |
| macOS with `terminal-notifier` | Native notification | Selects the exact pane when Ghostty tty lookup identifies the sole attached client; otherwise brings Ghostty forward. |
| macOS without `terminal-notifier` | `osascript display notification` | Informational only. |

Ghostty 1.3.1's macOS AppleScript dictionary lacks tty lookup. Newer builds may
provide it; the helper probes the running API rather than relying on a version
number. Unsupported APIs, non-Ghostty clients, shared sessions, linked windows,
and ambiguous matches receive a popup that activates Ghostty without selecting a
tmux session or pane. Ghostty is the fallback app even for detached sessions or
clients in other terminals.
No notification helper is installed automatically. On macOS, notification and
Ghostty Automation permissions are controlled by the OS.

An exact-target click focuses the matched Ghostty terminal and selects the exact tmux
pane. It rechecks the server, completion identity, client attachment, live pane
membership, and Ghostty terminal before navigating. Old notifications cannot
navigate to a later completion or a closed pane. A moved pane is followed only
within its original session. If another client is already attached or Ghostty cannot focus the
matched terminal, the click does nothing. If a client attaches while Ghostty is
being focused, tmux navigation is refused; the intended terminal may already have
been raised. Attention clears through the normal
focused-window rule, not directly from the callback.

Disable only popups:

```sh
tmux set -g @ai_notifications off
```

Restore them:

```sh
tmux set -g @ai_notifications on
```

The config defaults to `on` with `set -qog`, preserving runtime overrides across
reloads. Sound has its separate control below.

## Sound

The config defaults to `canberra-gtk-play -i complete` (Linux/libcanberra with a
sound theme containing the `complete` event). There is one asynchronous sound
command per scan containing new completions, so simultaneous completions are
coalesced. Sound failures don't stop monitoring. Tests replace the audio command
with a recorder and do not play audio.

Mute:

```sh
tmux set -g @ai_attention_command ''
```

Restore:

```sh
tmux set -g @ai_attention_command 'canberra-gtk-play -i complete'
```

Use another installed player if preferred:

```sh
tmux set -g @ai_attention_command 'pw-play /absolute/path/to/chime.oga'
```

This option is trusted local **shell code**, not agent-supplied text. Config uses
`set -qog` so reloading preserves runtime sound overrides without an already-set error. To apply a different
command immediately, use `set -g` as above rather than only editing the default.

## Verification and rollout

```sh
python3 -m unittest discover -s tests -v
sh -n stow/scripts/ai-spinner.sh
python3 -c 'from pathlib import Path; p = Path("stow/scripts/tmux-agent-notify"); compile(p.read_text(), str(p), "exec")'
git diff --check
```

The attention tests create private tmux servers and PTY clients. They exercise
real detection, indicators, picker rendering, acknowledgement, notifications,
in-flight reload/pane-movement races, status-only animation and bounded polling;
they never source the live config or run real AI agents. Verified with tmux 3.7c
and Linux `flock`. Notification tests record OS command boundaries and execute
captured callbacks against real private tmux servers; they do not show live
desktop popups. The attention suite also runs on macOS with tmux 3.8, BSD awk,
and the Python lock fallback, and on Linux with tmux 3.5a, mawk, and `flock`.
macOS and Linux notification commands use controlled fixtures. Native desktop
delivery, AppleScript permissions, and Ghostty focus still need a desktop smoke check.

For a Mac smoke check, use a private tmux socket in Ghostty with these scripts.
Run synthetic work in a background window, then confirm one native popup and an
unread check. Verify that clicking brings Ghostty forward on Ghostty 1.3.1; on a build with tty
lookup and `terminal-notifier`, click and confirm the exact window/tab and pane.
Repeat with two clients sharing the session; the click should activate Ghostty
without switching tmux panes. Close the target pane after receiving an exact-target
notification and confirm its click does nothing. Disable popups and confirm the check still works.
Stop that private server when finished.

A worktree checkout does **not** update existing Stow links: verify their actual
targets. Test in an isolated server first. Only after approving and applying the
change to the Stow source should you reload live tmux with `prefix q`. Upgrade the
script and format consumers together. For the first upgrade from a pre-lock
daemon, pause it with `tmux set -g @ai_spinner_pid paused`, verify that the old
daemon has exited, then reload; an old binary does not participate in the new
handover lock. Before live rollout, save copies of the current script and tmux
config. Rollback means restoring those two files and reloading; no sessions need
to be killed.
