#!/usr/bin/env bash

export DOTFILES=$HOME/.dotfiles

# include my library helpers for colorized echo and require_brew, etc
source $DOTFILES/bootstrap/lib/helpers.sh

# make a backup directory for overwritten dotfiles
if [[ ! -e ~/.dotfiles_backup ]]; then
    mkdir ~/.dotfiles_backup
fi


log "Hi. Time for magic!"

# Deal with ZSH things
echo $0 | grep zsh > /dev/null 2>&1 | true
if [[ ${PIPESTATUS[0]} != 0 ]]; then
  action "You should consider using zsh"
  if ask "install zsh"; then
    running "setting zsh to default shell"
    chsh -s $(which zsh)
  else
    log "Run this command: chsh -s $(which zsh)"
  fi
else
  log "looks like you're using zsh!"
fi

pushd ~ > /dev/null 2>&1

running "creating symlinks for project dotfiles..."
$DOTFILES/bootstrap/lib/symlink.sh

running "setting up vim"
$DOTFILES/bootstrap/lib/vim.sh

# Ruby
if ask "install ruby and rbenv"; then
  running "installing ruby and rbenv"
  $DOTFILES/bootstrap/lib/ruby.sh
fi

popd > /dev/null 2>&1

if mac; then
  log "You run a mac!"
  running "Setting up mac things"
  $DOTFILES/bootstrap/lib/macos.sh
fi


log "Woot! All done."
action "If this is default user, set DEFAULT_USER to whoami"
