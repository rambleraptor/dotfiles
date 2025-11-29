# Local path file
if [ -f "$DOTFILES/local/path.bash" ]; then
  source $DOTFILES/local/path.bash
fi

# Binary folders
export PATH=$PATH:$DOTFILES/bin

# Local binary folders
export PATH=$PATH:$DOTFILES/local/bin

eval "$(mise activate bash)"
