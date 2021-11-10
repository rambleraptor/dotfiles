# Adding Rbenv to PATH
if [ -d "$HOME/.rbenv" ]; then
  export PATH="$HOME/.rbenv/bin:$PATH"
  eval "$(rbenv init -)"
fi

# Binary folders
export PATH=$PATH:$DOTFILES/bin

# Local binary folders
export PATH=$PATH:$DOTFILES/local/bin
