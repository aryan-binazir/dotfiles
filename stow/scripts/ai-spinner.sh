#!/bin/sh
# Pin every command (including background scans) to the starting server.
socket=$(tmux display-message -p '#{socket_path}') || exit 1
tmux() { command tmux -S "$socket" "$@"; }

if [ "${1-}" != --locked ] && ! command -v flock >/dev/null 2>&1 && ! command -v python3 >/dev/null 2>&1; then
    exit 1
fi
if [ "${1-}" = --locked ]; then
    scan_dir=$2
else
    scan_dir=$(mktemp -d "${TMPDIR:-/tmp}/ai-spinner.XXXXXX") || exit 1
fi
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

if [ "${1-}" != --locked ]; then
    exec 9>"$socket.ai-spinner.lock" || exit 1
    if command -v flock >/dev/null 2>&1; then
        tmux set -g @ai_spinner_pid $$ || exit 1
        flock -x 9 || exit 1
    else
        exec python3 -c 'import fcntl, os, subprocess, sys
try:
    subprocess.run(["tmux", "-S", sys.argv[2], "set", "-g", "@ai_spinner_pid", str(os.getpid())], check=True)
    fcntl.flock(9, fcntl.LOCK_EX)
    os.set_inheritable(9, True)
    os.execv("/bin/sh", ["sh", sys.argv[1], "--locked", sys.argv[3]])
except BaseException:
    os.rmdir(sys.argv[3])
    raise' "$0" "$socket" "$scan_dir" || exit 1
    fi
fi

f0=⡇ f1=⠏ f2=⠛ f3=⠹ f4=⢸ f5=⣰ f6=⣤ f7=⣆
b0=$(printf '\342\240') b1=$(printf '\342\241')
b2=$(printf '\342\242') b3=$(printf '\342\243')
working="" working_s="" done_w="" done_s="" blocked_w="" blocked_s="" windows="" sessions="" clients=""
notify_script=""
if command -v python3 >/dev/null 2>&1; then
    notify_script=$(python3 -c 'from pathlib import Path; import sys; print(Path(sys.argv[1]).resolve().with_name("tmux-agent-notify"))' "$0")
fi

scan_panes() {
    pane_rows=$(tmux list-panes -a -F '#{session_id}|#{window_id}|#{pane_id}|#{pane_current_command}|#{pane_title}') || return 1
    while IFS='|' read -r sess win pane cmd title; do
        w=0 title_busy=0 agent=$cmd
        case $title in
        "$b0"* | "$b1"* | "$b2"* | "$b3"* | ◐* | ◑* | ◒* | ◓*) w=1 title_busy=1 ;;
        esac
        case $title in 'π - '*) agent=pi ;; esac
        case $agent in
            codex* | node | bun | uv | pi | cursor-agent | claude | [0-9]*.[0-9]*.[0-9]*)
                case $agent:$title in codex*:*'Action Required'* | node:*'Action Required'* | bun:*'Action Required'*)
                    printf '%s|%s|%s|blocked\n' "$sess" "$win" "$pane"
                    continue ;;
                esac
                content=$(tmux capture-pane -p -t "$pane" 2>/dev/null) || { printf '%s|%s|%s|unknown\n' "$sess" "$win" "$pane"; continue; }
                # C locale makes '.' consume the third UTF-8 byte of a braille glyph.
                w=$(printf '%s\n' "$content" | LC_ALL=C awk -v braille="$b0|$b1|$b2|$b3" -v command="$agent" -v title_busy="$title_busy" '
                    BEGIN {
                        pi = "^[[:space:]]*(" braille "). Working([.][.][.])?[[:space:]]*$"
                        native = (command ~ /^(claude|[0-9]+[.][0-9]+[.][0-9]+)$/)
                        claude = (native || command == "node" || command == "bun")
                        codex = (command ~ /^codex/ || command == "node" || command == "bun")
                        is_pi = (command == "pi" || command == "node" || command == "bun" || command == "uv")
                    }
                    {
                        line = tolower($0)
                        gsub(/ |│|┃/, " ", line)
                        sub(/^[[:space:]]+/, "", line)
                        sub(/[[:space:]]+$/, "", line)
                        if (line ~ /^(❯|›)([[:space:]]|$)/ &&
                            line !~ /^(❯|›)[[:space:]]*[0-9]+[.][[:space:]]/ &&
                            line !~ /^(❯|›)[[:space:]]*(accept|decline)([^a-z]|$)/) {
                            cancel = confirm = select_hint = options = question = mcp = accept = 0
                            last_prompt = n + 1
                        }
                        if (line != "") {
                            n++
                            screen[(n - 1) % 20] = line
                            position[(n - 1) % 20] = n
                            if (line ~ /^(❯|›|→)[[:space:]]*[^[:space:]]/) selected = n
                            if (line ~ /^(╭|┌|┏)?(─|━)(─|━)(─|━)/) border = n
                            if (line == "review your answers") review = n
                            if (is_pi && (selected > 0 && selected > n - 20 || border > 0 && border > n - 20 || review > 0 && review > n - 20)) {
                                if (line ~ /^(↑↓ navigate|enter submit|esc cancel · ↑↓ choose|ctrl\+c cancel · esc back|enter to submit all answers|1-9 select|space\/1-9 toggle|space toggle|↑↓ move)/) {
                                    pi_hint = line
                                    hint_start = n
                                } else if (hint_start && n <= hint_start + 2) pi_hint = pi_hint " " line
                                if (hint_start > selected && hint_start > border && hint_start > review &&
                                    (pi_hint ~ /^↑↓ navigate[[:space:]]+enter select[[:space:]]+(escape|esc|ctrl\+c).*cancel/ ||
                                     pi_hint ~ /^enter submit[[:space:]].*(escape|esc|ctrl\+c).*cancel/ ||
                                     pi_hint ~ /^esc cancel · ↑↓ choose · enter select/ ||
                                     pi_hint == "ctrl+c cancel · esc back · enter save" ||
                                     pi_hint == "enter to submit all answers" ||
                                     (pi_hint ~ /↑↓ move · enter confirm/ && pi_hint ~ /· esc cancel/) ||
                                     pi_hint == "enter submit · esc discard note · tab back")) pi_blocked = n
                            }
                            if (line ~ /(^|[[:space:]·])esc to cancel([[:space:]·]|$)/) cancel = n
                            if (line ~ /(^|[[:space:]·])enter to confirm([[:space:]·]|$)/) confirm = n
                            if (line ~ /enter to select/ && line ~ /navigate/) select_hint = n
                            if (line ~ /^(❯|›)?[[:space:]]*[123][.][[:space:]]+(yes|no)([^a-z]|$)/) options = n
                            if (line ~ /^(do you want to|would you like to) /) question = n
                            if (line ~ /^mcp server .+ requests your input$/) mcp = n
                            if (line ~ /^(❯)?[[:space:]]*(accept|decline)([^a-z]|$)/) accept = n
                        }
                    }
                    claude && /^(·|✢|✳|✶|✻|✽|[*]) [A-Za-z]+…([[:space:]]+[(][0-9]+[smh]([[:space:]]|[)])|[[:space:]]*$)/ { found = 1 }
                    !native && $0 ~ pi { found = 1; last_working = n }
                    !native && NF {
                        busy_line = ($0 ~ /[Ee]sc to interrupt|[Cc]trl[+][Cc] to stop|(^|[[:space:]])Working([.][.][.])?([[:space:]]|$)/)
                        recent[recent_n++ % 8] = busy_line
                        if (busy_line) last_working = n
                    }
                    END {
                        live = n - 20
                        blocked = (claude && cancel > live && cancel > 0 &&
                            (((confirm > live && confirm > 0) || (select_hint > live && select_hint > 0)) && selected > live && selected > 0 ||
                             (question > live && question > 0 && options > live && options > 0) ||
                             (mcp > live && mcp > 0 && accept > live && accept > 0)))
                        if (is_pi && pi_blocked > live && pi_blocked > last_working && pi_blocked > last_prompt) blocked = 1
                        for (i in screen) {
                            if (position[i] <= last_prompt) continue
                            line = screen[i]
                            if (codex && (selected > live && selected > 0 || border > live && border > 0) &&
                                (line == "press enter to confirm or esc to cancel" ||
                                line ~ /(^|[[:space:]·])enter to submit (answer|all)([[:space:]·]|$)/)) blocked = 1
                        }
                        if (blocked) { print "blocked"; exit }
                        if (found || title_busy) { print 1; exit }
                        for (i in recent) if (recent[i]) { print 1; exit }
                        print 0
                    }
                ') ;;
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
    ) 9>&- &
    scan_pid=$!
}

apply_scan() {
    wait "$scan_pid" 2>/dev/null
    scan_pid=""
    if [ "$(cat "$scan_ready" 2>/dev/null)" != ok ]; then
        rm -f "$scan_result" "$scan_ready"
        return
    fi
    # One snapshot avoids a fresh tmux process for every pane on every scan.
    pane_states=$(tmux list-panes -a -F '|#{pane_id}=#{@ai_attention_state}|') || return
    working="" working_s="" done_w="" done_s="" blocked_w="" blocked_s=""
    windows=$(tmux list-windows -a -F '#{window_id}' | sort -u)
    sessions=$(tmux list-sessions -F '#{session_id}')
    clients="" viewed=""
    client_rows=$(tmux list-clients -F '#{client_name}|#{window_id}|#{client_flags}|#{pane_in_mode}' 2>/dev/null)
    while IFS='|' read -r client window flags in_mode; do
        [ -n "$client" ] || continue
        case ",$flags," in *,control-mode,*) continue ;; esac
        clients="$clients $client"
        # Detached sessions, unfocused terminals, and picker/copy mode aren't
        # evidence that the user has actually looked at the agent's output.
        case ",$flags," in *,focused,*) ;; *) continue ;; esac
        [ "$in_mode" = 0 ] || continue
        viewed="$viewed $window"
    done <<EOF
$client_rows
EOF
    notify=0
    notify_panes=""
    processed_states=""
    while IFS='|' read -r sess win pane busy; do
        # Pane closure is not completion. Never update a reused/default target.
        case $pane in %*[!0-9]* | % | '') continue ;; %*) ;; *) continue ;; esac
        case $win in @*[!0-9]* | @ | '') continue ;; @*) ;; *) continue ;; esac
        # Linked windows reuse the state applied earlier in this scan; they
        # must neither advance debounce again nor aggregate the stale snapshot.
        case $processed_states in
        *"|$pane="*) entry=${processed_states#*"|$pane="}; busy=unknown ;;
        *)
            case $pane_states in
            *"|$pane="*) entry=${pane_states#*"|$pane="} ;;
            *) continue ;;
            esac ;;
        esac
        previous=${entry%%|*}
        state=$previous
        case $busy in
        blocked)
            case $previous in
            blocked-seen*) state=blocked-seen ;;
            *) state=blocked ;;
            esac ;;
        1) state=working ;;
        0)
            case $previous in
            working) state=quiet1 ;;
            quiet1) state=quiet2 ;;
            quiet2) state=done ;;
            blocked | blocked-seen) state=$previous-quiet1 ;;
            blocked-quiet1 | blocked-seen-quiet1) state=${previous%1}2 ;;
            blocked-quiet2 | blocked-seen-quiet2) state=done ;;
            esac ;;
        esac
        completed=0
        case $state in
        blocked)
            case $previous in blocked*) ;; *) completed=1 ;; esac ;;
        done)
            [ "$previous" = done ] || completed=1
            ;;
        esac
        case " $viewed " in *" $win "*)
            case $state in
            done) state="" ;;
            blocked | blocked-quiet1 | blocked-quiet2) state=blocked-seen${state#blocked} ;;
            esac ;;
        esac
        if [ "$state" != "$previous" ]; then
            # A pane can move after the async sample. Check membership and
            # persist together in tmux, never acknowledging its old window.
            event_command=""
            if [ "$completed" = 1 ]; then
                event_command="set-option -p -t $pane @ai_attention_event '$$:$tick' ; "
            fi
            applied=$(tmux if-shell -F -t "$pane" "#{==:#{window_id},$win}" \
                "set-option -p -t $pane @ai_attention_state '$state' ; ${event_command}display-message -p applied" \
                'display-message -p moved' 2>/dev/null) || continue
            [ "$applied" = applied ] || continue
            [ "$completed" = 0 ] || notify=1
            case $completed:$state in
            1:done | 1:blocked) notify_panes="$notify_panes $pane" ;;
            esac
        fi
        processed_states="$processed_states|$pane=$state|"
        case $state in
        working | quiet1 | quiet2)
            case " $working " in *" $win "*) ;; *) working="$working $win" ;; esac
            case " $working_s " in *" $sess "*) ;; *) working_s="$working_s $sess" ;; esac ;;
        done)
            case " $done_w " in *" $win "*) ;; *) done_w="$done_w $win" ;; esac
            case " $done_s " in *" $sess "*) ;; *) done_s="$done_s $sess" ;; esac ;;
        blocked | blocked-quiet1 | blocked-quiet2)
            case " $blocked_w " in *" $win "*) ;; *) blocked_w="$blocked_w $win" ;; esac
            case " $blocked_s " in *" $sess "*) ;; *) blocked_s="$blocked_s $sess" ;; esac ;;
        esac
    done < "$scan_result"
    if [ "$notify" = 1 ]; then
        sound_command=$(tmux show -gqv @ai_attention_command)
        if [ -n "$sound_command" ]; then
            sh -c "$sound_command" 9>&- </dev/null >/dev/null 2>&1 &
        fi
    fi
    if [ -n "$notify_panes" ] && [ -f "$notify_script" ] && command -v python3 >/dev/null 2>&1; then
        enabled=$(tmux show -gqv @ai_notifications)
        if [ "$enabled" != off ]; then
            for pane in $notify_panes; do
                python3 "$notify_script" notify --socket "$socket" --pane "$pane" --event "$$:$tick" 9>&- </dev/null >/dev/null 2>&1 &
            done
        fi
    fi
    rm -f "$scan_result" "$scan_ready"
}

tick=0
rendered=";"
frame_initialized=0
while :; do
    if [ $((tick % 4)) -eq 0 ]; then
        [ "$(tmux show -gqv @ai_spinner_pid 2>/dev/null)" = "$$" ] || exit 0
    fi
    if [ -f "$scan_ready" ]; then
        apply_scan
    fi
    if [ $((tick % 4)) -eq 0 ]; then
        [ -n "$scan_pid" ] || start_scan
    fi
    eval "frame=\$f$((tick % 8))"
    set --
    # Environment updates don't invalidate application panes like set-option.
    # Indicator options hold a format reference; only the status bar animates.
    if [ -n "$working" ] && { [ -n "$clients" ] || [ "$frame_initialized" = 0 ]; }; then
        set -- set-environment -gh TMUX_AI_SPINNER_FRAME "$frame" ';'
        frame_initialized=1
    fi
    next_rendered=";"
    # Even identical user-option writes can request full-client redraws. Only
    # publish changes, and queue a complete frame in one tmux command batch.
    for wnd in $windows; do
        icon=""
        case " $blocked_w " in *" $wnd "*) icon=" !" ;; esac
        case " $done_w " in *" $wnd "*) icon="$icon ✓" ;; esac
        case " $working " in *" $wnd "*) icon="$icon #{TMUX_AI_SPINNER_FRAME}" ;; esac
        key="w:$wnd=$icon;"
        next_rendered="$next_rendered$key"
        case $rendered in *";$key"*) ;; *)
            set -- "$@" set-option -w -t "$wnd" @ai_spinner "$icon" ';' ;;
        esac
    done
    for sess in $sessions; do
        icon=""
        case " $blocked_s " in *" $sess "*) icon="!" ;; esac
        case " $done_s " in *" $sess "*) icon="${icon:+$icon }✓" ;; esac
        case " $working_s " in *" $sess "*) icon="${icon:+$icon }#{TMUX_AI_SPINNER_FRAME}" ;; esac
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
