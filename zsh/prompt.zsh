autoload -U colors && colors
# cheers, @ehrenmurdick
# http://github.com/ehrenmurdick/config/blob/master/zsh/prompt.zsh

git_prompt(){
  # Check if the current directory is in a Git repository.
  if [[ "$(git rev-parse --is-inside-work-tree &>/dev/null; echo "${?}")" == '0' ]]; then

    # Get the short symbolic ref.
    # If HEAD isn’t a symbolic ref, get the short SHA for the latest commit
    # Otherwise, just give up.
    branchName="$(git symbolic-ref --quiet --short HEAD 2> /dev/null || \
      git rev-parse --short HEAD 2> /dev/null || \
      echo '(unknown)')";

    if [[ $(git status --porcelain) == "" ]]; then
      branchColor="%{$fg[green]%}"
    else
      branchColor="%{$fg_bold[red]%}"
    fi

    echo "(${branchColor}${branchName}%{$reset_color%})"

  else
    return;
  fi;
}

# Current Directory
directory_name() {
  echo "%{$fg[cyan]%}%~%{$reset_color%}"
}

cloud(){
  if grep -q "^flags.* hypervisor" /proc/cpuinfo 2> /dev/null; then
    echo "☁️  "
  else
    echo ""
  fi
}

server_name(){
  if [[ -n $DEFAULT_USER ]]; then
    echo "🚀  "
  else
    echo "$(cloud)[\u@\H]"
  fi
}

prompt_arrow(){
  echo "%{$fg_bold[magenta]%}›%{$reset_color%}"
}

# Actual prompt
export PROMPT=$'\n$(server_name)$(directory_name)$(git_prompt) $(prompt_arrow) '

precmd() {
  title "zsh" "%m" "%55<...<%~"
}
