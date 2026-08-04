#!/usr/bin/env bash

set -u

# jj keeps git HEAD permanently detached, so detached repos with a .jj dir get
# their label from jj instead: nearest first-ancestor bookmark (local or
# remote, preferring the local name), else the working-copy change id.
#
# jj calls cost ~120-150ms each, so labels are cached in a file keyed by repo
# root + HEAD content + jj operation head: every jj mutation (checkout,
# bookmark create, fetch) writes a new op head, so a cache hit means the
# label is still current. Cache misses run in parallel, one jj query per
# unique repo root.

cache_file=${XDG_CACHE_HOME:-$HOME/.cache}/tmux-branch-labels

git_branch() {
    local dir=$1
    local gitdir=
    local head=
    local parent=

    JJROOT=
    JJHEAD=

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
        if [[ -d $dir/.jj ]]; then
            JJROOT=$dir
            JJHEAD=$head
        fi
        REPLY="detached:${head:0:7}"
    else
        return 1
    fi
}

# Cache key for a jj repo: HEAD content + current op head(s). .jj/repo is a
# file (pointer to the real repo dir) in non-default workspaces.
jj_cache_key() {
    local root=$1
    local repo=$root/.jj/repo
    local -a ops=()
    local op

    if [[ -f $repo ]]; then
        IFS= read -r repo < "$repo" || return 1
        [[ $repo == /* ]] || repo=$root/.jj/$repo
    fi
    for op in "$repo"/op_heads/heads/*; do
        [[ -e $op ]] || continue
        ops+=("${op##*/}")
    done
    (( ${#ops[@]} )) || return 1
    # Shell pathname expansion is already sorted, so no Bash 4 `mapfile` is
    # needed here. Keeping the script Bash 3.2-compatible matters on macOS.
    REPLY="$JJHEAD:$(IFS=,; printf '%s' "${ops[*]}")"
}

jj_query() {
    local root=$1
    local out=$2
    local label=

    label=$(jj --ignore-working-copy -R "$root" log --no-graph \
        -r 'heads(first_ancestors(@) & (bookmarks() | remote_bookmarks()))' \
        -T 'if(local_bookmarks, local_bookmarks.join(","), remote_bookmarks.map(|r| r.name()).join(","))' 2>/dev/null) || return
    if [[ -z $label ]]; then
        label=$(jj --ignore-working-copy -R "$root" log --no-graph \
            -r '@' -T '"jj:" ++ change_id.shortest(8)' 2>/dev/null) || return
    fi
    [[ -n $label ]] && printf '%s\n' "$label" >| "$out"
}

declare -a session_ids=()
declare -a session_labels=() session_jjroots=()
declare -a cache_roots=() cache_keys=() cache_labels=()
declare -a jj_roots=() jj_keys=() jj_labels=() jj_outfiles=()
declare JJROOT= JJHEAD= jj_tmpdir= jjkey=
declare c_root c_key c_label
declare cache_index i j jj_index session_index

if [[ -r $cache_file ]]; then
    while IFS=$'\t' read -r c_root c_key c_label; do
        [[ -n $c_root && -n $c_key && -n $c_label ]] || continue
        cache_index=${#cache_roots[@]}
        cache_roots[$cache_index]=$c_root
        cache_keys[$cache_index]=$c_key
        cache_labels[$cache_index]=$c_label
    done < "$cache_file"
fi

while IFS=$'\t' read -r session_id session_path; do
    [[ -n $session_id ]] || continue
    session_index=${#session_ids[@]}
    session_ids[$session_index]=$session_id
    session_labels[$session_index]=
    session_jjroots[$session_index]=

    if [[ -d $session_path ]] && git_branch "$session_path"; then
        session_labels[$session_index]=$REPLY
        if [[ -n $JJROOT ]]; then
            session_jjroots[$session_index]=$JJROOT
            jj_index=-1
            for ((i = 0; i < ${#jj_roots[@]}; i++)); do
                if [[ ${jj_roots[$i]} == "$JJROOT" ]]; then
                    jj_index=$i
                    break
                fi
            done

            if ((jj_index < 0)); then
                jj_index=${#jj_roots[@]}
                jj_roots[$jj_index]=$JJROOT
                jj_labels[$jj_index]=
                jj_outfiles[$jj_index]=
                jjkey=$JJHEAD
                jj_cache_key "$JJROOT" && jjkey=$REPLY
                jj_keys[$jj_index]=$jjkey

                cache_index=-1
                for ((i = 0; i < ${#cache_roots[@]}; i++)); do
                    if [[ ${cache_roots[$i]} == "$JJROOT" && ${cache_keys[$i]} == "$jjkey" ]]; then
                        cache_index=$i
                        break
                    fi
                done

                if ((cache_index >= 0)); then
                    jj_labels[$jj_index]=${cache_labels[$cache_index]}
                else
                    if [[ -z $jj_tmpdir ]]; then
                        jj_tmpdir=$(mktemp -d 2>/dev/null) || jj_tmpdir=
                        [[ -n $jj_tmpdir ]] && trap 'rm -rf "$jj_tmpdir"' EXIT
                    fi
                    if [[ -n $jj_tmpdir ]]; then
                        jj_outfiles[$jj_index]=$jj_tmpdir/$jj_index
                        jj_query "$JJROOT" "${jj_outfiles[$jj_index]}" &
                    fi
                fi
            fi
        fi
    fi
done < <(tmux list-sessions -F $'#{session_id}\t#{session_path}' 2>/dev/null)

wait

declare root out label cache_dirty=0

for ((i = 0; i < ${#jj_roots[@]}; i++)); do
    out=${jj_outfiles[$i]:-}
    [[ -n $out && -s $out ]] || continue
    IFS= read -r label < "$out"
    jj_labels[$i]=$label

    cache_index=-1
    for ((j = 0; j < ${#cache_roots[@]}; j++)); do
        if [[ ${cache_roots[$j]} == "${jj_roots[$i]}" ]]; then
            cache_index=$j
            break
        fi
    done
    if ((cache_index < 0)); then
        cache_index=${#cache_roots[@]}
        cache_roots[$cache_index]=${jj_roots[$i]}
    fi
    cache_keys[$cache_index]=${jj_keys[$i]}
    cache_labels[$cache_index]=$label
    cache_dirty=1
done

if (( cache_dirty )); then
    mkdir -p "${cache_file%/*}" 2>/dev/null
    {
        for ((i = 0; i < ${#cache_roots[@]}; i++)); do
            printf '%s\t%s\t%s\n' "${cache_roots[$i]}" "${cache_keys[$i]}" "${cache_labels[$i]}"
        done
    } >| "$cache_file.$$" 2>/dev/null && mv -f "$cache_file.$$" "$cache_file" 2>/dev/null
fi

declare -a tmux_cmd=()

for ((i = 0; i < ${#session_ids[@]}; i++)); do
    session_id=${session_ids[$i]}
    label=${session_labels[$i]:-}
    root=${session_jjroots[$i]:-}
    if [[ -n $root ]]; then
        for ((j = 0; j < ${#jj_roots[@]}; j++)); do
            if [[ ${jj_roots[$j]} == "$root" && -n ${jj_labels[$j]:-} ]]; then
                label=${jj_labels[$j]}
                break
            fi
        done
    fi

    (( ${#tmux_cmd[@]} )) && tmux_cmd+=(\;)
    if [[ -n $label ]]; then
        tmux_cmd+=(set-option -q -t "$session_id" @branch "$label")
    else
        tmux_cmd+=(set-option -q -u -t "$session_id" @branch)
    fi
done

(( ${#tmux_cmd[@]} )) && tmux "${tmux_cmd[@]}" >/dev/null 2>&1
