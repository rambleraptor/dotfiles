#!/usr/bin/env bash

###########################
# This script installs the dotfiles and runs all other system configuration scripts
# Portions copyright @author Adam Eivy
###########################

DEFAULT_EMAIL="astephen2@gmail.com"
DEFAULT_GITHUBUSER="astephen2"

export DOTFILES=$HOME/.dotfiles


# include my library helpers for colorized echo and require_brew, etc
source $DOTFILES/bootstrap/lib.sh

# make a backup directory for overwritten dotfiles
if [[ ! -e ~/.dotfiles_backup ]]; then
    mkdir ~/.dotfiles_backup
fi

bot "Hi. I'm going to make your OSX system better. But first, I need to configure this project based on your info"

fullname=`osascript -e "long user name of (system info)"`

if [[ -n "$fullname" ]];then
  lastname=$(echo $fullname | awk '{print $2}');
  firstname=$(echo $fullname | awk '{print $1}');
fi

# me=`dscl . -read /Users/$(whoami)`

if [[ -z $lastname ]]; then
  lastname=`dscl . -read /Users/$(whoami) | grep LastName | sed "s/LastName: //"`
fi
if [[ -z $firstname ]]; then
  firstname=`dscl . -read /Users/$(whoami) | grep FirstName | sed "s/FirstName: //"`
fi
email=`dscl . -read /Users/$(whoami)  | grep EMailAddress | sed "s/EMailAddress: //"`

if [[ ! "$firstname" ]];then
  response='n'
else
  echo -e "I see that your full name is $COL_YELLOW$firstname $lastname$COL_RESET"
  read -r -p "Is this correct? [Y|n] " response
fi

if [[ $response =~ ^(no|n|N) ]];then
  read -r -p "What is your first name? " firstname
  read -r -p "What is your last name? " lastname
fi
fullname="$firstname $lastname"

bot "Great $fullname, "

if [[ ! $email ]];then
  response='n'
else
  echo -e "The best I can make out, your email address is $COL_YELLOW$email$COL_RESET"
  read -r -p "Is this correct? [Y|n] " response
fi

if [[ $response =~ ^(no|n|N) ]];then
  read -r -p "What is your email? [$DEFAULT_EMAIL] " email
  if [[ ! $email ]];then
    email=$DEFAULT_EMAIL
  fi
fi

grep 'user = atomantic' $HOME/.gitconfig
if [[ $? = 0 ]]; then
    read -r -p "What is your github.com username? [$DEFAULT_GITHUBUSER]" githubuser
fi
if [[ ! $githubuser ]];then
  githubuser=$DEFAULT_GITHUBUSER
fi

running "replacing items in .gitconfig with your info ($COL_YELLOW$fullname, $email, $githubuser$COL_RESET)"

# test if gnu-sed or osx sed

sed -i 's/Adam Eivy/'$firstname' '$lastname'/' .gitconfig > /dev/null 2>&1 | true
if [[ ${PIPESTATUS[0]} != 0 ]]; then
  echo
  running "looks like you are using OSX sed rather than gnu-sed, accommodating"
  sed -i '' 's/Alex Stephen/'$firstname' '$lastname'/' $HOME/.gitconfig;
  sed -i '' 's/astephen2@gmail.com/'$email'/' $HOME/.gitconfig;
  sed -i '' 's/astephen2/'$githubuser'/' $HOME/.gitconfig;
  sed -i '' 's/Alex/'$(whoami)'/g' $HOME/.zshrc;ok
else
  echo
  bot "looks like you are already using gnu-sed. woot!"
  sed -i 's/astephen2@gmail.com/'$email'/' .gitconfig;
  sed -i 's/astephen2/'$githubuser'/' .gitconfig;
  sed -i 's/Alex/'$(whoami)'/g' .zshrc;ok
fi

# read -r -p "OK? [Y/n] " response
#  if [[ ! $response =~ ^(yes|y|Y| ) ]];then
#     exit 1
#  fi

# bot "awesome. let's roll..."

echo $0 | grep zsh > /dev/null 2>&1 | true
if [[ ${PIPESTATUS[0]} != 0 ]]; then
  running "changing your login shell to zsh"
  chsh -s $(which zsh);ok
else
  bot "looks like you are already using zsh. woot!"
fi

pushd ~ > /dev/null 2>&1

bot "creating symlinks for project dotfiles..."

$DOTFILES/bootstrap/symlink.sh

popd > /dev/null 2>&1

if [ "$(uname)" == "Darwin" ]; then
  $DOTFILES/bootstrap/osx.sh
fi

running "adding vundle for vim"
git clone https://github.com/VundleVim/Vundle.vim.git ~/.vim/bundle/Vundle.vim

bot "Woot! All done."
