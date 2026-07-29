#!/bin/sh
# ai-spinner.sh — daemon that flags windows where an AI agent is working and
# animates a 4-dot spinner in the status line.
#
# Started from tmux.conf via `run-shell -b`; singleton enforced through the
# @ai_spinner_pid global option. Windows get @ai_spinner set to the current
# frame (displayed via #{@ai_spinner} in window-status-format); sessions with
# any working window get @ai_spinner_s (shown in the choose-tree session list).
#
# Detection (once per second, asynchronously):
#   Claude Code — sets its pane title to a braille char (U+2800–U+28FF) while
#                 working, "✳ ..." while waiting for input.
#   codex       — pane content shows "esc to interrupt" while working.
#   pi          — pane content shows "Working" / "Working..." while working
#                 (marker taken from the earlier tmux-agent-status attempt).
#
# Animation (every ~167ms): frame advances one position and clients are
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
scan_dir=$(mktemp -d "${TMPDIR:-/tmp}/ai-spinner.XXXXXX") || exit 1
scan_result="$scan_dir/result"
scan_ready="$scan_dir/ready"
scan_pid=""

cleanup() {
    if [ -n "$scan_pid" ]; then
        kill "$scan_pid" 2>/dev/null
        wait "$scan_pid" 2>/dev/null
    fi
    rm -f "$scan_result" "$scan_ready"
    rmdir "$scan_dir" 2>/dev/null
}
trap cleanup 0
trap 'exit 0' HUP INT TERM

scan_panes() {
    new=""
    new_s=""
    pane_rows=$(tmux list-panes -a -F '#{session_id}|#{window_id}|#{pane_id}|#{pane_current_command}|#{pane_title}') ||
        return 1

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
$pane_rows
EOF

    printf '%s\n%s\n%s\n' \
        "${new# }" \
        "${new_s# }" \
        "$(tmux list-clients -F '#{client_name}' 2>/dev/null)"
}

start_scan() {
    rm -f "$scan_result" "$scan_ready"
    (
        if scan_panes > "$scan_result"; then
            printf 'ok\n' > "$scan_ready"
        else
            printf 'failed\n' > "$scan_ready"
        fi
    ) &
    scan_pid=$!
}

apply_scan() {
    wait "$scan_pid" 2>/dev/null
    scan_pid=""

    if [ "$(cat "$scan_ready" 2>/dev/null)" != ok ]; then
        rm -f "$scan_result" "$scan_ready"
        return
    fi

    new=$(sed -n '1p' "$scan_result")
    new_s=$(sed -n '2p' "$scan_result")
    clients=$(sed -n '3,$p' "$scan_result")

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

    working=$new
    working_s=$new_s
    rm -f "$scan_result" "$scan_ready"
}

tick=0
while :; do
    if [ -f "$scan_ready" ]; then
        apply_scan
    fi

    if [ $((tick % 6)) -eq 0 ]; then
        tmux has-session 2>/dev/null || exit 0
        [ "$(tmux show -gqv @ai_spinner_pid)" = "$$" ] || exit 0

        [ -n "$scan_pid" ] || start_scan
    fi

    if [ -n "$working" ] || [ "$need_clear" = 1 ]; then
        eval "frame=\$f$((tick % 8))"
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
    sleep 0.1667
done
