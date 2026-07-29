#!/bin/sh
# ai-spinner.sh — daemon that flags windows where an AI agent is working and
# animates a 4-dot spinner in the status line.
#
# Started from tmux.conf via `run-shell -b`; singleton enforced through the
# @ai_spinner_pid global option. Windows get @ai_spinner set to the current
# frame (displayed via #{@ai_spinner} in window-status-format); sessions with
# any working window get @ai_spinner_s (shown in the choose-tree session list).
#
# Detection (once per second):
#   Claude Code — sets its pane title to a braille char (U+2800–U+28FF) while
#                 working, "✳ ..." while waiting for input.
#   codex       — pane content shows "esc to interrupt" while working.
#   pi          — pane content shows "Working" / "Working..." while working
#                 (marker taken from the earlier tmux-agent-status attempt).
#
# Animation (every 125ms): frame advances by two positions and clients are
# refreshed with refresh-client -S, so rotation stays quick without needing
# a high refresh rate.

# Claim the singleton slot; a previously running daemon notices the pid
# change on its next detection tick and exits on its own (killing it here
# would make tmux print "terminated by signal 15" on every config reload).
tmux set -g @ai_spinner_pid $$ || exit 1

# Clear any flags a previous instance left behind
for w in $(tmux list-windows -a -F '#{window_id}'); do
    tmux set -w -t "$w" -u @ai_spinner 2>/dev/null
done
for s in $(tmux list-sessions -F '#{session_id}'); do
    tmux set -t "$s" -u @ai_spinner_s 2>/dev/null
done

f0=⡇ f1=⠏ f2=⠛ f3=⠹ f4=⢸ f5=⣰ f6=⣤ f7=⣇

# UTF-8 prefixes covering the braille block (E2 A0 80 .. E2 A3 BF)
b0=$(printf '\342\240') b1=$(printf '\342\241')
b2=$(printf '\342\242') b3=$(printf '\342\243')

working=""
working_s=""
need_clear=0
tick=0
while :; do
    if [ $((tick % 8)) -eq 0 ]; then
        tmux has-session 2>/dev/null || exit 0
        [ "$(tmux show -gqv @ai_spinner_pid)" = "$$" ] || exit 0

        new=""
        new_s=""
        while IFS='|' read -r sess win pane cmd title; do
            case " $new " in *" $win "*) continue ;; esac
            w=0
            case $title in
            "$b0"* | "$b1"* | "$b2"* | "$b3"*) w=1 ;;
            *)
                case $cmd in
                codex*) tmux capture-pane -p -t "$pane" 2>/dev/null |
                    tail -8 | grep -qi 'esc to interrupt' && w=1 ;;
                uv | pi) tmux capture-pane -p -t "$pane" 2>/dev/null |
                    tail -8 | grep -qE '(^|[[:space:]])Working(\.\.\.)?([[:space:]]|$)' && w=1 ;;
                esac
                ;;
            esac
            if [ $w -eq 1 ]; then
                new="$new $win"
                case " $new_s " in *" $sess "*) ;; *) new_s="$new_s $sess" ;; esac
            fi
        done <<EOF
$(tmux list-panes -a -F '#{session_id}|#{window_id}|#{pane_id}|#{pane_current_command}|#{pane_title}')
EOF
        for wnd in $working; do
            case " $new " in *" $wnd "*) ;; *)
                tmux set -w -t "$wnd" -u @ai_spinner 2>/dev/null
                need_clear=1
                ;;
            esac
        done
        for s in $working_s; do
            case " $new_s " in *" $s "*) ;; *)
                tmux set -t "$s" -u @ai_spinner_s 2>/dev/null
                need_clear=1
                ;;
            esac
        done
        working=${new# }
        working_s=${new_s# }
        clients=$(tmux list-clients -F '#{client_name}' 2>/dev/null)
    fi

    if [ -n "$working" ] || [ "$need_clear" = 1 ]; then
        eval "frame=\$f$(((tick * 2) % 8))"
        for wnd in $working; do
            tmux set -w -t "$wnd" @ai_spinner " $frame" 2>/dev/null
        done
        for s in $working_s; do
            tmux set -t "$s" @ai_spinner_s "$frame" 2>/dev/null
        done
        for c in $clients; do
            tmux refresh-client -S -t "$c" 2>/dev/null
        done
        need_clear=0
    fi

    tick=$((tick + 1))
    sleep 0.125
done
