COMP_COLOR="$fg[cyan]"
PWD_COLOR="$fg[yellow]"
GIT_DIRTY_COLOR="$fg[red]"
GIT_CLEAN_COLOR="$fg[green]"
PYTHON_COLOR="$fg[magenta]"


PROMPT='
$COMP_COLOR%m: $PWD_COLOR$(get_pwd)$(put_spacing)$(git_prompt_info)$(python_env)
$reset_color→ '

#Git Prefix, suffix, colors
ZSH_THEME_GIT_PROMPT_PREFIX="[git:"
ZSH_THEME_GIT_PROMPT_DIRTY="$GIT_DIRTY_COLOR+"
ZSH_THEME_GIT_PROMPT_CLEAN="$GIT_CLEAN_COLOR"
ZSH_THEME_END_SUFFIX="]$reset_color"

ZSH_THEME_PYTHON_PROMPT_PREFIX="[python:"
function get_pwd() {
   echo "${PWD/$HOME/~}"
}

function put_spacing() {

	#Calculate number of places for git prompt
	local git=$(git_prompt_info)
	if [ ${#git} != 0 ]; then
    	((git=${#git} -10))
	else
    	git=0
	fi

	#Calculate number of places for python env
	local pythonenv=$VIRTUAL_ENV
	if [ ${#pythonenv} != 0 ]; then
		((pythonenv=${#VIRTUAL_ENV} -7))
	else
		pythonenv=0
	fi
	#Calculate the proper number of spaces
	local termwidth
	(( termwidth = ${COLUMNS} - ${#HOST} - ${#$(get_pwd)} - ${git} -${pythonenv}))
	#Create string with proper number of spaces
	local spacing=""
	for i in {1..$termwidth}; do
    	spacing="${spacing} "
	done
	echo $spacing
}

function git_prompt_info() {
   ref=$(git symbolic-ref HEAD 2> /dev/null) || return
   echo "$(parse_git_dirty)$ZSH_THEME_GIT_PROMPT_PREFIX$(current_branch)$ZSH_THEME_END_SUFFIX"
}

function python_env() {
    [ $VIRTUAL_ENV ] && echo "$PYTHON_COLOR$ZSH_THEME_PYTHON_PROMPT_PREFIX`basename $VIRTUAL_ENV`$ZSH_THEME_END_SUFFIX"
}
