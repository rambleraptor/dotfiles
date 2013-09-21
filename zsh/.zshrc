# Path to your oh-my-zsh configuration.
ZSH=$HOME/.oh-my-zsh
ZSH_THEME="alex"

plugins=(git)
source $ZSH/oh-my-zsh.sh

#Virtualenv
source /usr/local/bin/virtualenvwrapper.sh
export VIRTUAL_ENV_DISABLE_PROMPT=1

#Path
export PATH=$PATH:/opt/local/bin:/opt/local/sbin:/opt/local/bin:/opt/local/sbin:/Users/Alex/.rvm/gems/ruby-1.9.2-p290/bin:/Users/Alex/.rvm/gems/ruby-1.9.2-p290@global/bin:/Users/Alex/.rvm/rubies/ruby-1.9.2-p290/bin:/Users/Alex/.rvm/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/Users/Alex/Documents/Open/Chromium/depot_tools:/opt/X11/bin

#Functions
function myip() {
    ifconfig lo0 | grep 'inet ' | sed -e 's/:/ /' | awk '{print "lo0       : " $2}'
    ifconfig en0 | grep 'inet ' | sed -e 's/:/ /' | awk '{print "en0 (IPv4): " $2 " " $3 " " $4 " " $5 " " $6}'
    ifconfig en0 | grep 'inet6 ' | sed -e 's/ / /' | awk '{print "en0 (IPv6): " $2 " " $3 " " $4 " " $5 " " $6}'
    ifconfig en1 | grep 'inet ' | sed -e 's/:/ /' | awk '{print "en1 (IPv4): " $2 " " $3 " " $4 " " $5 " " $6}'
    ifconfig en1 | grep 'inet6 ' | sed -e 's/ / /' | awk '{print "en1 (IPv6): " $2 " " $3 " " $4 " " $5 " " $6}'
}

function hiddenOn() { defaults write com.apple.Finder AppleShowAllFiles YES ; }
function hiddenOff() { defaults write com.apple.Finder AppleShowAllFiles NO ; }

#Golang Stuff
export GOROOT=/usr/local/Cellar/go/1.1.1

export GOPATH=$HOME/.go
export PATH=$PATH:$GOPATH/bin

alias go='nocorrect go'

#Java Stuff
export CLASSPATH=/Users/Alex/Documents/School/EECS285
#Autojump
[[ -s `brew --prefix`/etc/autojump.sh ]] && . `brew --prefix`/etc/autojump.sh

#Local files
if [ -r ~/.dotfiles/zsh/.zshrc.local ]; then
    . ~/.dotfiles/zsh/.zshrc.local
fi





