#!/usr/bin/env bash

export DOTFILES=$HOME/.dotfiles

# include my library helpers for colorized echo and require_brew, etc
source $DOTFILES/bootstrap/lib/helpers.sh

# make a backup directory for overwritten dotfiles
if [[ ! -e ~/.dotfiles_backup ]]; then
    mkdir ~/.dotfiles_backup
fi

log "Hi. Time for magic!"
log "Updating your submodules"

git submodule init
git submodule update --force

pushd ~ > /dev/null 2>&1

running "creating symlinks for project dotfiles..."
$DOTFILES/bootstrap/lib/symlink.sh

for installer in $(find $DOTFILES -name "install.sh" -print | \
grep -v "macos" | \
grep -v "bootstrap"); do
  program=$(dirname $installer | xargs basename)
  if ask "setup $program"; then
    sh -c ${installer}
  fi
done

if mac; then
  log "You're running on a mac!"
  sh -c $DOTFILES/macos/install.sh
fi

log "Woot! All done."
action "If this is default user, set DEFAULT_USER to whoami"
action "You should use zsh. Run 'chsh -s $(which zsh)' to make that happen"
