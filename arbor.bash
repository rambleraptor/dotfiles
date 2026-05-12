# Arbor shell integration
# This allows 'arbor cd <name>' to actually change your directory.

function arbor() {
  if [[ "$1" == "cd" || "$1" == "c" ]]; then
    if [[ -n "$2" ]]; then
      local target
      target=$(command arbor cd "$2" 2>/dev/null)
      if [[ -n "$target" ]]; then
        cd "$target"
        return $?
      else
        command arbor "$@"
      fi
    else
      command arbor "$@"
    fi
  else
    command arbor "$@"
  fi
}
