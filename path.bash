# Adding Rbenv to PATH
if [ -d "$HOME/.rbenv" ]; then
  export PATH="$HOME/.rbenv/bin:$PATH"
  eval "$(rbenv init -)"
fi

# Adding Go to PATH
if [ -d "$HOME/go" ]; then
  export GOPATH="$HOME/go"
  export PATH="$PATH:$HOME/go/bin"
fi

# Binary folders
export PATH=$PATH:$DOTFILES/bin

# Local binary folders
export PATH=$PATH:$DOTFILES/local/bin
