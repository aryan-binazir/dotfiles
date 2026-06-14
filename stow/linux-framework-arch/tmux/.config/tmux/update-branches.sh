#!/bin/bash

set -u

git_branch() {
	local dir=$1
	local gitdir=
	local head=
	local parent=

	while [[ -n $dir ]]; do
		if [[ -d $dir/.git ]]; then
			gitdir=$dir/.git
			break
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
		[[ $parent == $dir ]] && return 1
		dir=$parent
	done

	[[ -n $gitdir && -r $gitdir/HEAD ]] || return 1
	IFS= read -r head < "$gitdir/HEAD" || return 1

	if [[ $head == "ref: refs/heads/"* ]]; then
		REPLY=${head#ref: refs/heads/}
	elif [[ $head == "ref: "* ]]; then
		REPLY=${head#ref: }
	elif [[ -n $head ]]; then
		REPLY="detached:${head:0:7}"
	else
		return 1
	fi
}

declare -a tmux_cmd=()

while IFS=$'\t' read -r session_id session_path; do
	[[ -n $session_id ]] || continue
	(( ${#tmux_cmd[@]} )) && tmux_cmd+=(\;)

	if [[ -d $session_path ]] && git_branch "$session_path"; then
		tmux_cmd+=(set-option -q -t "$session_id" @branch "$REPLY")
	else
		tmux_cmd+=(set-option -q -u -t "$session_id" @branch)
	fi
done < <(tmux list-sessions -F $'#{session_id}\t#{session_path}' 2>/dev/null)

(( ${#tmux_cmd[@]} )) && tmux "${tmux_cmd[@]}" >/dev/null 2>&1
