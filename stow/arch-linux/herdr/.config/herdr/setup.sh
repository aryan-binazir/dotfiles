#!/usr/bin/env bash
set -eu
die() { echo "setup.sh: $*" >&2; exit 1; }
src=$(cd "$(dirname "$0")" && pwd -P)
case $(git -C "$src" rev-parse --git-dir 2>/dev/null) in
*/worktrees/*) die "run from the permanent checkout" ;;
esac
cfg=$HOME/.config/herdr
for d in "$cfg" "$cfg/plugins" "$cfg/plugins/config"; do ! [ -L "$d" ] || die "$d is a symlink"; done
mkdir -p "$cfg/plugins/config" "$HOME/.local/bin"
list=$(herdr plugin list)
has() { case $list in *"$1"*) return 0 ;; esac; return 1; }
link() {
  [ -L "$2" ] && [ "$2" -ef "$1" ] && return
  ! [ -e "$2" ] && ! [ -L "$2" ] || die "$2 exists; not replacing"
  ln -sn "$1" "$2"
}
install() {
  has "disabled [github:$1@" && return
  has "github:$1@$2" || MISE_TRUSTED_CONFIG_PATHS=$cfg/plugins herdr plugin install "$1" ${2:+--ref "$2"}
}

for p in confirm-close last-workspace; do
  link "$src/plugins/$p" "$cfg/plugins/$p"
  state=--enabled
  has "disabled [local:$src/plugins/$p]" && state=--disabled
  herdr plugin link "$cfg/plugins/$p" "$state"
done
link "$src/config.toml" "$cfg/config.toml"
link "$(cd "$src/../../../../scripts" && pwd -P)/hm" "$HOME/.local/bin/hm"
# Directory link: the plugin saves model-selection.json by atomic replacement.
link "$src/plugins/config/tab-smart-rename" "$cfg/plugins/config/tab-smart-rename"

install aryan-binazir/herdr-triage "$(git ls-remote https://github.com/aryan-binazir/herdr-triage HEAD | cut -f1)" # Cargo
install jhochenbaum/herdr-hunk-diff ac5eef7cec6a65fbf8f0c9bbd61b4383489beba5 # Node 22.12+
install ChmaraX/herdr-nvim 26cd43e38126be8012b59f95fd41ef33574d0d08 # nvim 0.10+
install iurysza/herdr-tab-smart-rename 37a4c89e0dc35d234b8381337eced577eb517f8b # Bun 1.2.23+ on the server PATH
