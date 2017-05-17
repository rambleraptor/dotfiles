#!/usr/bin/env bash

export DOTFILES=$HOME/.dotfiles

# include my library helpers for colorized echo and require_brew, etc
source $DOTFILES/bootstrap/lib/helpers.sh

# make a backup directory for overwritten dotfiles
if [[ ! -e ~/.dotfiles_backup ]]; then
    mkdir ~/.dotfiles_backup
fi

bot "Hi. I'm going to make system better. But first, I need to configure this project based on your info"

echo $0 | grep zsh > /dev/null 2>&1 | true
if [[ ${PIPESTATUS[0]} != 0 ]]; then
  running "changing your login shell to zsh"
  chsh -s $(which zsh);ok
else
  bot "looks like you are already using zsh. woot!"
fi

pushd ~ > /dev/null 2>&1

bot "creating symlinks for project dotfiles..."

$DOTFILES/bootstrap/lib/symlink.sh

running "setting up vim"
$DOTFILES/bootstrap/lib/vim.sh

popd > /dev/null 2>&1

if mac; then
  running "You run a mac! 😃 "
  running "Setting up mac things"
  $DOTFILES/bootstrap/lib/macos.sh
fi


bot "Woot! All done."
action "If this is default user, set DEFAULT_USER to whoami"
