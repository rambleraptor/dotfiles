# Adding Rbenv to PATH
if [ -d "$HOME/.rbenv" ]; then
  export PATH="$HOME/.rbenv/bin:$PATH"
  eval "$(rbenv init -)"
fi

# Adding pyenv to PATH
if [ -d "$HOME/.pyenv" ]; then
  export PYENV_ROOT="$HOME/.pyenv"
  export PATH="$PYENV_ROOT/bin:$PATH"
fi

# Adding Go to PATH
if [ -d "$HOME/go" ]; then
  export GOPATH="$HOME/go"
  export PATH="$PATH:$HOME/go/bin"
fi

# Local path file
if [ -f "$DOTFILES/local/path.bash" ]; then
  source $DOTFILES/local/path.bash
fi

# Binary folders
export PATH=$PATH:$DOTFILES/bin

# Local binary folders
export PATH=$PATH:$DOTFILES/local/bin
