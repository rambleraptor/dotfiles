#!/usr/bin/env bash

source $HOME/.dotfiles/script/lib/helpers.sh
# Vim Setup

log "Time to setup vim"
log "Please use vim once before installation."

mkdir -p $HOME/.vim/backups
mkdir -p $HOME/.vim/swaps
mkdir -p $HOME/.vim/undo

# Install vim-plug if not found already.
if [ ! -f "$HOME/.vim/autoload/plug.vim" ]; then
  if ask "Install vim-plug?"; then
    mkdir -p $HOME/.vim/autoload

    curl -fLo ~/.vim/autoload/plug.vim --create-dirs \
      https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim

    vim +'PlugInstall --sync' +qa
  fi
fi

ok "Vim setup complete"
