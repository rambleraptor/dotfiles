#!/bin/bash

$HOME/.dotfiles/bootstrap/lib/macos/homebrew.sh

if ask "enable macosx defaults"; then
  running "enabling osx defaults"
  $HOME/.dotfiles/bootstrap/lib/macos/defaults.sh
fi
