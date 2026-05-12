export LSCOLORS="exfxcxdxbxegedabagacad"
export CLICOLOR=true

HISTFILE=~/.bash_history
HISTSIZE=10000
HISTFILESIZE=10000
HISTCONTROL=ignoreboth:erasedups
HISTTIMEFORMAT='%F %T '

shopt -s histappend         # append rather than overwrite history on exit
shopt -s cmdhist            # store multi-line commands as one entry
shopt -s checkwinsize       # update LINES/COLUMNS after each command
shopt -s no_empty_cmd_completion
