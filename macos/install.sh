#!/bin/bash
source $DOTFILES/bootstrap/lib/helpers.sh

if ask "install homebrew"; then
  $HOME/.dotfiles/bootstrap/lib/macos/homebrew.sh
fi

if ask "enable macosx defaults"; then
  running "enabling osx defaults"
  $HOME/.dotfiles/bootstrap/lib/macos/defaults.sh
fi
