#!/bin/bash

set -u

checkout_name() {
local dir=$1
local gitdir=
local head=
local label=
local parent=

while [[ -n $dir ]]; do
if [[ -d $dir/.git ]]; then
return 1
fi

if [[ -f $dir/.git ]]; then
IFS= read -r head < "$dir/.git" || return 1
[[ $head == "gitdir: "* ]] || return 1
gitdir=${head#gitdir: }
[[ $gitdir == /* ]] || gitdir=$dir/$gitdir
break
fi

parent=${dir%/*}
[[ -n $parent ]] || parent=/
[[ $parent == "$dir" ]] && return 1
dir=$parent
done

[[ $gitdir == */worktrees/* ]] || return 1
[[ -f $gitdir/commondir ]] || return 1
[[ -r $gitdir/HEAD ]] || return 1
IFS= read -r head < "$gitdir/HEAD" || return 1

case $head in
"ref: refs/heads/"*) label=${head#ref: refs/heads/} ;;
"ref: "*) label=${head#ref: } ;;
?*) label="detached:${head:0:7}" ;;
*) return 1 ;;
esac

case $label in
aryanbinazir/*) label=${label#aryanbinazir/} ;;
aryan-binazir/*) label=${label#aryan-binazir/} ;;
esac

[[ -n $label ]] || return 1

if (( ${#label} > 24 )); then
REPLY="${label:0:23}…"
else
REPLY=$label
fi
}

if [[ ${1:-} == --name ]]; then
dir=${2:-}
if [[ $dir != /* ]]; then
[[ -d $dir ]] || exit 1
dir=$(cd -- "$dir" && pwd) || exit 1
fi
checkout_name "$dir" || exit 1
printf '%s\n' "$REPLY"
exit 0
fi

cleanup() {
local owner=
local snapshot=
local window_id=
local managed=

owner=$(tmux show-option -gqv @window_checkout_names_pid 2>/dev/null) || return
[[ $owner == $$ ]] || return

snapshot=$(tmux list-windows -a -F $'#{window_id}\x1f#{@window_checkout_name_managed}' 2>/dev/null) || return
while IFS=$'\x1f' read -r window_id managed; do
[[ -n $window_id ]] || continue
[[ $managed == 1 ]] || continue
tmux set-window-option -u -t "$window_id" @window_checkout_name_managed \; set-window-option -u -t "$window_id" automatic-rename-format \; set-window-option -t "$window_id" automatic-rename on 2>/dev/null || true
done <<< "$snapshot"
tmux if-shell -F "#{==:#{@window_checkout_names_pid},$$}" 'set-option -gu @window_checkout_names_pid' 2>/dev/null || true
}

trap cleanup EXIT
trap 'exit 0' INT TERM HUP
tmux set-option -g @window_checkout_names_pid $$ || exit 1

# Keep the write end open so the empty pipe blocks read until its timeout.
exec {sleep_fd}<> <(:)

fmt=$'#{@window_checkout_names_pid}\x1f#{window_id}\x1f#{pane_current_path}\x1f#{pane_current_command}\x1f#{automatic-rename}\x1f#{@window_checkout_name_managed}\x1f#{window_name}'

while :; do
snapshot=$(tmux list-windows -a -F "$fmt") || exit 0

while IFS=$'\x1f' read -r owner window_id path command automatic managed current; do
[[ -n $window_id ]] || continue
[[ $owner == $$ ]] || exit 0

if checkout_name "$path"; then
if [[ $managed == 1 && $automatic == 0 && $current != "$REPLY" ]]; then
tmux set-window-option -u -t "$window_id" @window_checkout_name_managed \; set-window-option -u -t "$window_id" automatic-rename-format 2>/dev/null || true
continue
fi

if [[ $managed == 1 || $automatic == 1 || $current == "$REPLY" ]]; then
if [[ $managed != 1 || $automatic != 1 || $current != "$REPLY" ]]; then
tmux_args=()
if [[ $current != "$REPLY" ]]; then
name=$REPLY
[[ $name == *';' ]] && name=${name%';'}'\;'
tmux_args+=(rename-window -t "$window_id" -- "$name" \;)
fi
tmux_args+=(set-window-option -t "$window_id" automatic-rename-format '#{window_name}' \;)
tmux_args+=(set-window-option -t "$window_id" automatic-rename on \;)
tmux_args+=(set-window-option -t "$window_id" @window_checkout_name_managed 1)
tmux "${tmux_args[@]}" 2>/dev/null || true
fi
fi
elif [[ $managed == 1 ]]; then
name=$command
[[ $name == *';' ]] && name=${name%';'}'\;'
tmux set-window-option -u -t "$window_id" @window_checkout_name_managed \; set-window-option -u -t "$window_id" automatic-rename-format \; rename-window -t "$window_id" -- "$name" \; set-window-option -t "$window_id" automatic-rename on 2>/dev/null || true
fi
done <<< "$snapshot"

read -rt 1 -u "$sleep_fd" _ || true
done
