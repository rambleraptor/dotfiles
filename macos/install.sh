#!/bin/bash
source $DOTFILES/bootstrap/lib/helpers.sh

for file in $DOTFILES/macos/install/*
do
  filename=$(basename "$file")
  filename="${filename%.*}"
  if ask "run $filename"; then
    sh -c $file
  fi
done
