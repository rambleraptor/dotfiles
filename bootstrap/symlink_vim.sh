#!/bin/bash
# include my library helpers for colorized echo and require_brew, etc
source $DOTFILES/bootstrap/lib.sh

for source in `find ~/.dotfiles -path ~/.dotfiles/vim -prune -o -name '*.vim' -print`
do
  filename=`basename ${source}`
  running "Symlinking file $filename"
  ln -s $source ~/.vim/ftplugin/$filename
done
