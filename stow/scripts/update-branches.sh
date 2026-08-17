#!/bin/bash

set -u

LC_ALL=C
start_dir=$PWD

git_branch() {
	local dir=$1
	local gitdir=
	local head=

	# Resolve symlinks so the lexical .git walk matches what git would find.
	# Anchor relative paths to the script's start dir: cd -P moves our cwd,
	# so a later relative session_path must not resolve against it.
	[[ $dir == /* ]] || dir=$start_dir/$dir
	CDPATH= builtin cd -P -- "$dir" 2>/dev/null || return 1
	dir=$PWD

	while :; do
		if [[ -d $dir/.git ]]; then
			gitdir=$dir/.git
			break
		fi

		if [[ -f $dir/.git ]]; then
			IFS= read -r head < "$dir/.git"
			[[ $head == "gitdir: "* ]] || return 1
			gitdir=${head#gitdir: }
			[[ $gitdir == /* ]] || gitdir=$dir/$gitdir
			break
		fi

		[[ $dir == / ]] && return 1
		dir=${dir%/*}
		[[ -n $dir ]] || dir=/
	done

	[[ -r $gitdir/HEAD ]] || return 1
	IFS= read -r head < "$gitdir/HEAD"

	if [[ $head == "ref: refs/heads/"?* ]]; then
		REPLY=${head#ref: refs/heads/}
	elif [[ $head == "ref: refs/"?* ]]; then
		REPLY=${head#ref: }
	elif [[ $head =~ ^[0-9a-fA-F]{40}([0-9a-fA-F]{24})?$ ]]; then
		REPLY="detached:${head:0:7}"
	else
		return 1
	fi
}

declare -a tmux_cmd=()

# \x1f delimiter: tab is IFS whitespace, so it would collapse the empty
# #{@branch} field; a non-whitespace IFS char preserves empty fields.
while IFS=$'\x1f' read -r session_id current session_path; do
	[[ -n $session_id ]] || continue

	branch=
	if [[ -n $session_path ]]; then
		git_branch "$session_path" && branch=$REPLY
	fi

	[[ $branch == "$current" ]] && continue
	(( ${#tmux_cmd[@]} )) && tmux_cmd+=(\;)

	if [[ -n $branch ]]; then
		# tmux drops a bare trailing semicolon argument as a command separator.
		[[ $branch == *\; ]] && branch=${branch%;}'\;'
		tmux_cmd+=(set-option -q -t "$session_id" @branch "$branch")
	else
		tmux_cmd+=(set-option -q -u -t "$session_id" @branch)
	fi
done < <(tmux list-sessions -F $'#{session_id}\x1f#{@branch}\x1f#{session_path}' 2>/dev/null)

if (( ${#tmux_cmd[@]} )); then
	tmux "${tmux_cmd[@]}" >/dev/null 2>&1
fi
