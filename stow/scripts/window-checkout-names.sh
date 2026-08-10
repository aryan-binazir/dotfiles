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
[[ -n $gitdir && -r $gitdir/HEAD ]] || return 1
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

if (( ${#label} > 24 )); then
REPLY="${label:0:23}…"
else
REPLY=$label
fi
}

if [[ ${1:-} == --name ]]; then
checkout_name "${2:-}" || exit 1
printf '%s\n' "$REPLY"
exit 0
fi

tmux set-option -g @window_checkout_names_pid $$ || exit 1

while :; do
tmux has-session 2>/dev/null || exit 0
[[ $(tmux show-option -gqv @window_checkout_names_pid) == $$ ]] || exit 0

while IFS=$'\x1f' read -r window_id active path command automatic managed current; do
[[ $active == 1 ]] || continue

if checkout_name "$path"; then
if [[ $managed == 1 && $automatic == 0 && $current != "$REPLY" ]]; then
tmux set-window-option -u -t "$window_id" @window_checkout_name_managed
tmux set-window-option -u -t "$window_id" automatic-rename-format
continue
fi

if [[ $managed == 1 || $automatic == 1 || $current == "$REPLY" ]]; then
if [[ $current != "$REPLY" ]]; then
tmux rename-window -t "$window_id" "$REPLY"
fi
if [[ $managed != 1 || $automatic == 0 || $current != "$REPLY" ]]; then
tmux set-window-option -t "$window_id" automatic-rename-format '#{window_name}'
fi
if [[ $automatic == 0 || $current != "$REPLY" ]]; then
tmux set-window-option -t "$window_id" automatic-rename on
fi
if [[ $managed != 1 ]]; then
tmux set-window-option -t "$window_id" @window_checkout_name_managed 1
fi
fi
elif [[ $managed == 1 ]]; then
tmux set-window-option -u -t "$window_id" @window_checkout_name_managed
tmux set-window-option -u -t "$window_id" automatic-rename-format
tmux rename-window -t "$window_id" "$command"
tmux set-window-option -t "$window_id" automatic-rename on
fi
done < <(tmux list-panes -a -F $'#{window_id}\x1f#{pane_active}\x1f#{pane_current_path}\x1f#{pane_current_command}\x1f#{automatic-rename}\x1f#{@window_checkout_name_managed}\x1f#{window_name}')

sleep 1
done
