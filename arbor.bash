# Arbor shell integration
# This allows 'arbor cd <name>' to actually change your directory, and drops you
# into a freshly created worktree after 'arbor research'.

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
  elif [[ "$1" == "research" ]]; then
    # 'research' prints the new worktree path to stdout (messages go to stderr),
    # so capture it and cd in on success.
    local target
    target=$(command arbor "$@")
    local rc=$?
    if [[ $rc -eq 0 && -n "$target" ]]; then
      cd "$target"
      return $?
    fi
    return $rc
  else
    command arbor "$@"
  fi
}
