if [ "$(uname)" "==" "Darwin" ]; then
    [[ -s `brew --prefix`/etc/autojump.zsh ]] && . `brew --prefix`/etc/autojump.zsh
fi
