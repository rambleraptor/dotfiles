if [ "$(uname -s)" = "Darwin" ]; then
    [[ -s `brew --prefix`/etc/autojump.sh ]] && . `brew --prefix`/etc/autojump.sh
fi 
