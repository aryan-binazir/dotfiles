# .bashrc

# Source global definitions
if [ -f /etc/bashrc ]; then
    . /etc/bashrc
fi

# User specific environment
if ! [[ "$PATH" =~ "$HOME/.local/bin:$HOME/bin:" ]]; then
    PATH="$HOME/.local/bin:$HOME/bin:$PATH"
fi
export PATH

# Uncomment the following line if you don't like systemctl's auto-paging feature:
# export SYSTEMD_PAGER=

# User specific aliases and functions
if [ -d ~/.bashrc.d ]; then
    for rc in ~/.bashrc.d/*; do
        if [ -f "$rc" ]; then
            . "$rc"
        fi
    done
fi
unset rc

export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"  # This loads nvm
[ -s "$NVM_DIR/bash_completion" ] && \. "$NVM_DIR/bash_completion"  # This loads nvm bash_completion

# Environment Variables
export EDITOR=nvim
export VISUAL=nvim
export BROWSER=firefox
export TERMINAL=alacritty

# Source API keys from separate file
if [ -f "$HOME/.api_keys" ]; then
    source "$HOME/.api_keys"
fi

# Source aliases from dotfiles if available
if [ -f "$HOME/repos/dotfiles/other/aliases" ]; then
    source "$HOME/repos/dotfiles/other/aliases"
else
    # Fallback aliases
    alias python=python3
    alias venv='source ~/.venv/bin/activate'
    alias vi=nvim
    alias vim=nvim
    alias lg=lazygit
    alias repos='cd ~/repos'
    alias update="sudo dnf update -y && sudo dnf upgrade -y && flatpak update -y && sudo snap refresh && claude update && npm -g update"
    alias claude="~/.claude/local/claude --dangerously-skip-permissions"

    # alias tm='~/.local/bin/tm'
fi

# Additional useful aliases
alias ll='ls -alF'
alias la='ls -A'
alias l='ls -CF'
alias ..='cd ..'
alias ...='cd ../..'
alias ....='cd ../../..'
alias gs='git status'
alias ga='git add'
alias gc='git commit'
alias gp='git push'
alias gl='git log --oneline --graph --decorate'
alias gd='git diff'

# Directory shortcuts
alias dot='cd ~/repos/dotfiles'
alias obs='cd ~/Obsidian'
alias dl='cd ~/Downloads'

# System shortcuts
alias reload='source ~/.bashrc'
alias path='echo -e ${PATH//:/\\n}'

# Add custom scripts to PATH
export PATH="$HOME/repos/dotfiles/tmux/scripts:$PATH"
export PATH="$HOME/repos/dotfiles/other/scripts:$PATH"

# Prompt customization
# Git branch in prompt
parse_git_branch() {
    git branch 2> /dev/null | sed -e '/^[^*]/d' -e 's/* \(.*\)/ (\1)/'
}

# Custom prompt with colors
# Format: [user@host dir](git-branch)$ 
export PS1='\[\033[01;32m\]\u\[\033[00m\] λ \[\033[01;34m\]\W\[\033[33m\]$(parse_git_branch)\[\033[00m\]\$ '

# Enable color support for ls and grep
if [ -x /usr/bin/dircolors ]; then
    test -r ~/.dircolors && eval "$(dircolors -b ~/.dircolors)" || eval "$(dircolors -b)"
    alias ls='ls --color=auto'
    alias grep='grep --color=auto'
    alias fgrep='fgrep --color=auto'
    alias egrep='egrep --color=auto'
fi

# History settings
export HISTSIZE=10000
export HISTFILESIZE=20000
export HISTCONTROL=ignoreboth:erasedups
shopt -s histappend

# Useful functions
mkcd() {
    mkdir -p "$1" && cd "$1"
}

extract() {
    if [ -f "$1" ]; then
        case "$1" in
            *.tar.bz2) tar xjf "$1" ;;
            *.tar.gz) tar xzf "$1" ;;
            *.bz2) bunzip2 "$1" ;;
            *.rar) unrar e "$1" ;;
            *.gz) gunzip "$1" ;;
            *.tar) tar xf "$1" ;;
            *.tbz2) tar xjf "$1" ;;
            *.tgz) tar xzf "$1" ;;
            *.zip) unzip "$1" ;;
            *.Z) uncompress "$1" ;;
            *.7z) 7z x "$1" ;;
            *) echo "'$1' cannot be extracted via extract()" ;;
        esac
    else
        echo "'$1' is not a valid file"
    fi
}


# For Bottles
export MOZ_ENABLE_WAYLAND=1
export QT_QPA_PLATFORM=wayland

