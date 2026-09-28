#!/bin/sh
# Agent detection is deliberately heuristic: ✓ means "check this agent", not
# success. Keep the existing title/text detection and 250ms spinner animation.
# Pane attention lives in tmux options, so config/daemon reloads do not lose it.

# Pin every command (including background scans) to the starting server.
socket=$(tmux display-message -p '#{socket_path}') || exit 1
tmux() { command tmux -S "$socket" "$@"; }

# Replacement instances claim ownership; the previous instance exits on a tick.
tmux set -g @ai_spinner_pid $$ || exit 1
f0=⡇ f1=⠏ f2=⠛ f3=⠹ f4=⢸ f5=⣰ f6=⣤ f7=⣆
b0=$(printf '\342\240') b1=$(printf '\342\241')
b2=$(printf '\342\242') b3=$(printf '\342\243')
working="" working_s="" done_w="" done_s="" windows="" sessions="" clients=""
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
    pane_rows=$(tmux list-panes -a -F '#{session_id}|#{window_id}|#{pane_id}|#{pane_current_command}|#{pane_title}') || return 1
    while IFS='|' read -r sess win pane cmd title; do
        w=0
        case $title in
        "$b0"* | "$b1"* | "$b2"* | "$b3"*) w=1 ;;
        *)
            case $cmd in
            codex* | node | bun | uv | pi | cursor-agent)
                content=$(tmux capture-pane -p -t "$pane" 2>/dev/null) || { printf '%s|%s|%s|unknown\n' "$sess" "$win" "$pane"; continue; }
                # Pi's todo/footer widgets can push its busy line above the
                # last eight rows. Match only its standalone braille+Working
                # status across the visible pane, not arbitrary chat mentions.
                # C locale makes '.' consume the third UTF-8 braille byte.
                if printf '%s\n' "$content" | LC_ALL=C grep -qE "^[[:space:]]*($b0|$b1|$b2|$b3). Working(\.\.\.)?[[:space:]]*$"; then
                    w=1
                else
                    printf '%s\n' "$content" | grep -v '^[[:space:]]*$' | tail -8 |
                        grep -qE '[Ee]sc to interrupt|[Cc]trl\+[Cc] to stop|(^|[[:space:]])Working(\.\.\.)?([[:space:]]|$)' && w=1
                fi ;;
            esac
            ;;
        esac
        printf '%s|%s|%s|%s\n' "$sess" "$win" "$pane" "$w"
    done <<EOF
$pane_rows
EOF
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
    working="" working_s="" done_w="" done_s=""
    windows=$(tmux list-windows -a -F '#{window_id}' | sort -u)
    sessions=$(tmux list-sessions -F '#{session_id}')
    clients=$(tmux list-clients -F '#{client_name}' 2>/dev/null)
    viewed=""
    client_rows=$(tmux list-clients -F '#{window_id}|#{client_flags}|#{pane_in_mode}' 2>/dev/null)
    while IFS='|' read -r window flags in_mode; do
        # Detached sessions, unfocused terminals, and picker/copy mode aren't
        # evidence that the user has actually looked at the agent's output.
        case ",$flags," in *,focused,*) ;; *) continue ;; esac
        case ",$flags," in *,control-mode,*) continue ;; esac
        [ "$in_mode" = 0 ] || continue
        viewed="$viewed $window"
    done <<EOF
$client_rows
EOF
    notify=0
    processed=""
    while IFS='|' read -r sess win pane busy; do
        # Pane closure is not completion. Never update a reused/default target.
        case $pane in %*[!0-9]* | % | '') continue ;; %*) ;; *) continue ;; esac
        previous=$(tmux show -pqv -t "$pane" @ai_attention_state 2>/dev/null) || continue
        # Linked windows appear once per session; advance their panes only once.
        case " $processed " in *" $pane "*) busy=unknown ;; *) processed="$processed $pane" ;; esac
        state=$previous
        case $busy in
        1) state=working ;;
        # Three quiet observations, about two seconds apart from first to last,
        # avoid treating a single redraw as completion. Persist the debounce too.
        0)
            case $previous in
            working) state=quiet1 ;;
            quiet1) state=quiet2 ;;
            quiet2) state=done ;;
            esac ;;
        esac
        completed=0
        if [ "$state" = done ]; then
            [ "$previous" = done ] || completed=1
            case " $viewed " in *" $win "*) state="" ;; esac
        fi
        if [ "$state" != "$previous" ]; then
            tmux set -p -t "$pane" @ai_attention_state "$state" 2>/dev/null || continue
            [ "$completed" = 0 ] || notify=1
        fi
        case $state in
        working | quiet1 | quiet2)
            case " $working " in *" $win "*) ;; *) working="$working $win" ;; esac
            case " $working_s " in *" $sess "*) ;; *) working_s="$working_s $sess" ;; esac ;;
        done)
            case " $done_w " in *" $win "*) ;; *) done_w="$done_w $win" ;; esac
            case " $done_s " in *" $sess "*) ;; *) done_s="$done_s $sess" ;; esac ;;
        esac
    done < "$scan_result"
    if [ "$notify" = 1 ]; then
        sound_command=$(tmux show -gqv @ai_attention_command)
        if [ -n "$sound_command" ]; then
            sh -c "$sound_command" </dev/null >/dev/null 2>&1 &
        fi
    fi
    rm -f "$scan_result" "$scan_ready"
}

tick=0
rendered=";"
while :; do
    [ "$(tmux show -gqv @ai_spinner_pid 2>/dev/null)" = "$$" ] || exit 0
    if [ -f "$scan_ready" ]; then
        apply_scan
    fi
    if [ $((tick % 4)) -eq 0 ]; then
        tmux has-session 2>/dev/null || exit 0
        [ -n "$scan_pid" ] || start_scan
    fi
    eval "frame=\$f$((tick % 8))"
    set --
    next_rendered=";"
    # Even identical user-option writes can request full-client redraws. Only
    # publish changes, and queue a complete frame in one tmux command batch.
    for wnd in $windows; do
        icon=""
        case " $done_w " in *" $wnd "*) icon=" ✓" ;; esac
        case " $working " in *" $wnd "*) icon="$icon $frame" ;; esac
        key="w:$wnd=$icon;"
        next_rendered="$next_rendered$key"
        case $rendered in *";$key"*) ;; *)
            set -- "$@" set-option -w -t "$wnd" @ai_spinner "$icon" ';' ;;
        esac
    done
    for sess in $sessions; do
        icon=""
        case " $done_s " in *" $sess "*) icon="✓" ;; esac
        case " $working_s " in *" $sess "*) icon="${icon:+$icon }$frame" ;; esac
        key="s:$sess=$icon;"
        next_rendered="$next_rendered$key"
        case $rendered in *";$key"*) ;; *)
            set -- "$@" set-option -t "$sess" @ai_spinner_s "$icon" ';' ;;
        esac
    done
    if [ "$#" -gt 0 ]; then
        for client in $clients; do
            set -- "$@" refresh-client -S -t "$client" ';'
        done
        if tmux "$@" 2>/dev/null; then
            rendered=$next_rendered
        else
            rendered=";"
        fi
    else
        rendered=$next_rendered
    fi
    tick=$((tick + 1))
    sleep 0.25
done
