#!/bin/bash
# include my library helpers for colorized echo and require_brew, etc
source $HOME/.dotfiles/bootstrap/lib/helpers.sh

running "Installing tmux plugins"
~/.tmux/plugins/tpm/bin/install_plugins
