#!/bin/bash
# include my library helpers for colorized echo and require_brew, etc
source $HOME/.dotfiles/bootstrap/lib/helpers.sh

running "adding vundle because submodules are awful"
mkdir -p ~/.vim/bundle
git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim

running "Symlinking all of the vim files"
for source in `find ~/.dotfiles -path ~/.dotfiles/vim -prune -o -name '*.vim' -print`
do
  filename=`basename ${source}`
  running "Symlinking file $filename\n"
  ln -s $source ~/.vim/ftplugin/$filename
done

running "installing vundle plugins"
vim +PluginInstall +qall!
