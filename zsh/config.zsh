
# Source Prezto.
if [[ -s "${ZDOTDIR:-$HOME}/.zprezto/init.zsh" ]]; then
    source "${ZDOTDIR:-$HOME}/.zprezto/init.zsh"
fi

#Virtualenv
if [ -r /usr/local/bin/virtualenvwrapper.sh ]; then
    source /usr/local/bin/virtualenvwrapper.sh
    export VIRTUAL_ENV_DISABLE_PROMPT=1
fi

#Local files
if [ -r ${HOME}/.dotfiles/zsh/.zshrc.local ]; then
    . ~/.dotfiles/zsh/.zshrc.local
fi



