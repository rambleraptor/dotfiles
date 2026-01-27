# Arbor shell integration
# This allows 'arbor cd <name>' to actually change your directory.

function arbor() {
  if [[ "$1" == "cd" || "$1" == "c" ]]; then
    if [[ -n "$2" ]]; then
      # Try to get the path from arbor
      local target
      # We use 'command arbor' to bypass this function and call the actual binary
      target=$(command arbor cd "$2" 2>/dev/null)
      if [[ -n "$target" ]]; then
        cd "$target"
        return $?
      else
        # If arbor cd fails, fall back to normal execution to show error
        command arbor "$@"
      fi
    else
      command arbor "$@"
    fi
  else
    command arbor "$@"
  fi
}
