#!/bin/bash
# include my library helpers for colorized echo and require_brew, etc
source $HOME/.dotfiles/bootstrap/lib/helpers.sh

running "installing rbenv"
if mac; then
  log "You run a mac! Using homebrew"
  require_brew "rbenv"
else 
  log "Installing rbenv manually"
  git clone https://github.com/rbenv/rbenv.git ~/.rbenv
  cd ~/.rbenv && src/configure && make -C src
  git clone https://github.com/rbenv/ruby-build.git ~/.rbenv/plugins/ruby-build
fi

action "you may have to restart your shell"

log "Installing Ruby 2.7.0 takes absolutely forever"
if ask "install ruby 2.7.0"; then
  running "getting ruby 2.7.0. This is going to take forever"
  rbenv install 2.7.0
fi
