#!/bin/bash
source $DOTFILES/bootstrap/lib/helpers.sh

if ask "install homebrew"; then
  $HOME/.dotfiles/install/homebrew.sh
fi

if ask "enable macosx defaults"; then
  running "enabling osx defaults"
  $HOME/.dotfiles/macos/install/defaults.sh
fi
