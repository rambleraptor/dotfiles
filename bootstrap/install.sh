#!/usr/bin/env bash

export DOTFILES=$HOME/.dotfiles

# include my library helpers for colorized echo and require_brew, etc
source $DOTFILES/bootstrap/lib/helpers.sh

# make a backup directory for overwritten dotfiles
if [[ ! -e ~/.dotfiles_backup ]]; then
    mkdir ~/.dotfiles_backup
fi

log "Hi. Time for magic!"
pushd ~ > /dev/null 2>&1

# Symlink all proper files.
running "creating symlinks for project dotfiles..."
$DOTFILES/bootstrap/lib/symlink.sh

# Install vim-plug
if [ ! -f "$HOME/.vim/autoload/plug.vim" ]; then
  if ask "Install vim-plug?"; then
    curl -fLo ~/.vim/autoload/plug.vim --create-dirs \
      https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim
  fi
fi
