autoload -U colors && colors
# cheers, @ehrenmurdick
# http://github.com/ehrenmurdick/config/blob/master/zsh/prompt.zsh

# Git Prompt
if (( $+commands[git] ))
then
  git="$commands[git]"
else
  git="/usr/bin/git"
fi

git_branch() {
  echo $($git symbolic-ref HEAD 2>/dev/null | awk -F/ {'print $NF'})
}

git_dirty() {
  if $(! $git status -s &> /dev/null)
  then
    echo ""
  else
    if [[ $($git status --porcelain) == "" ]]
    then
      echo "(%{$fg[green]%}$(git_prompt_info)%{$reset_color%})"
    else
      echo "(%{$fg_bold[red]%}$(git_prompt_info)%{$reset_color%})"
    fi
  fi
}

git_prompt_info () {
 ref=$($git symbolic-ref HEAD 2>/dev/null) || return
# echo "(%{\e[0;33m%}${ref#refs/heads/}%{\e[0m%})"
 echo "${ref#refs/heads/}"
}

unpushed () {
  $git cherry -v @{upstream} 2>/dev/null
}

need_push () {
  if [[ $(unpushed) == "" ]]
  then
    echo " "
  else
    echo " with %{$fg_bold[magenta]%}unpushed%{$reset_color%} "
  fi
}

# Ruby Prompt
ruby_version() {
  if (( $+commands[rbenv] ))
  then
    echo "$(rbenv version | awk '{print $1}')"
  fi

  if (( $+commands[rvm-prompt] ))
  then
    echo "$(rvm-prompt | awk '{print $1}')"
  fi
}

rb_prompt() {
  if ! [[ -z "$(ruby_version)" ]]
  then
    echo "%{$fg_bold[yellow]%}$(ruby_version)%{$reset_color%} "
  else
    echo ""
  fi
}

# Current Directory
directory_name() {
  echo "%{$fg[cyan]%}%~%{$reset_color%}"
}

# Current Username
server_name(){
  local user=`whoami`
  if [[ "$user" != "$DEFAULT_USER" || -n "$SSH_CONNECTION" ]]
  then
    echo "%F{blue}[$USER@%m]%f "
  elif [[ "$(uname -s)" == "Darwin" ]]
  then
    echo "🚀  ";
  else
    echo "";
  fi
}

prompt_arrow(){
  echo "%{$fg_bold[magenta]%}›%{$reset_color%}"
}
extra_spaces(){
  PROMPT_SPACE=$(server_name)
  if [[ $PROMPT_SPACE == *"🚀 "* ]] then
    echo "  "
  else
    echo " "
  fi
}

# Actual prompt
export PROMPT=$'\n$(server_name)$(directory_name)$(git_dirty)$(need_push)\n$(prompt_arrow)$(extra_spaces)'
set_prompt () {
  export RPROMPT="%{$fg[magenta]%}%{$reset_color%}"
}

precmd() {
  title "zsh" "%m" "%55<...<%~"
  set_prompt
}



