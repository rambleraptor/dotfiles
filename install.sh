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

# Install vim-plug if not found already.
if [ ! -f "$HOME/.vim/autoload/plug.vim" ]; then
  if ask "Install vim-plug?"; then
    mkdir -p $HOME/.vim/autoload

    curl -fLo ~/.vim/autoload/plug.vim --create-dirs \
      https://raw.githubusercontent.com/junegunn/vim-plug/master/plug.vim

    vim +'PlugInstall --sync' +qa
  fi
fi

# Install tpm for tmux
if type tmux >/dev/null 2>/dev/null; then
  if [[ ! -e "$HOME/.tmux/plugins/tpm" ]]; then
    if ask "Install tpm (tmux package manager)?"; then
      git clone https://github.com/tmux-plugins/tpm ~/.tmux/plugins/tpm
    fi
  fi
fi
