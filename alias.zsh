# Easier navigation: .., ..., ...., ....., ~ and -
alias ..="cd .."
alias ...="cd ../.."
alias ....="cd ../../.."
alias .....="cd ../../../.."
alias -- -="cd -"

# git aliases
alias g="git"
alias master="git checkout master"
alias gaa="git add --all"
alias gca="git commit --amend"

alias gerrit="git push origin HEAD:refs/for/master --recurse-submodules=no"

# copy file interactive
alias cp='cp -i'

# move file interactive
alias mv='mv -i'

# untar
alias untar='tar xvf'

# homebrew
alias cask='brew cask'
