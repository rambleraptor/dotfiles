# Arbor shell integration for Bash
# This allows 'arbor cd <name>' to actually change your directory.

arbor() {
  if [[ "$1" == "cd" || "$1" == "c" ]]; then
    if [[ -n "$2" ]]; then
      # Try to get the path from arbor
      local target
      # We use 'command arbor' to bypass this function and call the actual binary
      # Use the absolute path if DOTFILES is set to be extra safe
      if [[ -n "$DOTFILES" ]]; then
        target=$("$DOTFILES/bin/arbor" cd "$2" 2>/dev/null)
      else
        target=$(command arbor cd "$2" 2>/dev/null)
      fi

      if [[ -n "$target" ]]; then
        cd "$target"
        return $?
      else
        # If arbor cd fails, fall back to normal execution to show error
        if [[ -n "$DOTFILES" ]]; then
          "$DOTFILES/bin/arbor" "$@"
        else
          command arbor "$@"
        fi
      fi
    else
      if [[ -n "$DOTFILES" ]]; then
        "$DOTFILES/bin/arbor" "$@"
      else
        command arbor "$@"
      fi
    fi
  else
    if [[ -n "$DOTFILES" ]]; then
      "$DOTFILES/bin/arbor" "$@"
    else
      command arbor "$@"
    fi
  fi
}
