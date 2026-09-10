# ramblerator dotfiles

![iTerm Screenshot](https://raw.githubusercontent.com/astephen2/dotfiles/master/docs/dotfiles.png)

These are the dotfiles that I use on my personal machine. The goal of this repo is to create a completely automated process to setup a new machine with my settings and applications.

# Install Scripts

This repo contains the following install scripts:

* `script/install.sh`: The main install script. Symlinks all files together. Used for GitHub Codespaces.
* `script/symlink.sh`: Symlinks all files together.
* `script/mac_defaults.sh`: Registry changes for Mac OS systems.



# Agent Skills

Skills for coding agents live in `skills/`, one directory per skill:

```
skills/<name>/SKILL.md
```

They are installed with the [skills CLI](https://github.com/vercel-labs/skills)
by `task skills:install`, which is part of `task install`. To add a new one:

```bash
cd skills && npx -y skills@latest init <name>   # scaffold
$EDITOR <name>/SKILL.md                         # write it
task skills:install                             # install for Claude Code
```

The install task picks up whatever `skills/` contains, so adding a skill needs
no change to the Taskfile. Skills are copied into `~/.claude/skills`, so re-run
`task skills:install` after editing one. `task skills:list` shows what is
currently installed.
