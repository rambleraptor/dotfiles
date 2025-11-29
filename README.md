# ramblerator dotfiles

![iTerm Screenshot](https://raw.githubusercontent.com/rambleraptor/dotfiles/master/docs/dotfiles.png)

These are the dotfiles that I use on my personal machine. The goal of this repo is to create a completely automated process to setup a new machine with my settings and applications.

## Features

- **Automated Setup**: One-command installation for new machines
- **Cross-platform**: Supports macOS and Linux
- **Task-based**: Uses [go-task](https://taskfile.dev) for organized installation
- **Modern Tools**: Includes mise, starship, tmux, neovim, and more
- **Customizable**: Easy to extend and customize for your needs

## Quick Start

### Bootstrap Installation

For a fresh machine setup, run:

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/rambleraptor/dotfiles/main/bootstrap.sh)
```

This will:
1. Install Homebrew (macOS only)
2. Clone this repository to `~/.dotfiles`
3. Install all dependencies
4. Symlink configuration files
5. Apply macOS defaults (macOS only)

### Manual Installation

If you prefer to install manually:

```bash
# Clone the repository
git clone https://github.com/rambleraptor/dotfiles.git ~/.dotfiles
cd ~/.dotfiles

# Run the install script
./install
```

## Prerequisites

### macOS
- macOS 10.15 (Catalina) or later
- Xcode Command Line Tools (installed automatically by Homebrew)

### Linux
- Recent Linux distribution with bash/zsh
- curl and git installed

## What's Included

### Applications (via Homebrew)

**CLI Tools:**
- `gh` - GitHub CLI
- `go-task` - Task runner
- `jq` / `yq` - JSON/YAML processors
- `mise` - Runtime version manager
- `neovim` - Modern vim
- `starship` - Cross-shell prompt
- `tmux` - Terminal multiplexer

**macOS Apps:**
- 1Password - Password manager
- Flux - Screen color temperature
- Ghostty - Terminal emulator
- Google Chrome - Web browser
- Rectangle - Window management
- Spotify - Music streaming
- Visual Studio Code - Code editor

### Dotfiles

- **Zsh**: Shell configuration with custom settings
- **Vim/Neovim**: Sensible defaults with plugins
- **Tmux**: Terminal multiplexing with vim keybindings
- **Git**: Comprehensive aliases and settings
- **Starship**: Beautiful cross-shell prompt
- **Mise**: Runtime version management

## Configuration Structure

```
.dotfiles/
├── packages/          # Package-specific configurations
│   ├── git/          # Git config
│   ├── mise/         # Mise config
│   ├── starship/     # Starship prompt
│   ├── tmux/         # Tmux config
│   ├── vim/          # Vim config
│   └── zsh/          # Zsh config
├── tasks/            # Task definitions
│   ├── brew.yml      # Homebrew tasks
│   ├── mac-defaults.yml  # macOS defaults
│   ├── mise.yml      # Mise setup
│   └── symlink.yml   # Symlinking tasks
├── bin/              # Custom scripts
├── local/            # Machine-specific configs (gitignored)
├── Brewfile          # Homebrew packages
├── Taskfile.yml      # Main task definitions
├── bootstrap.sh      # Bootstrap script
└── install           # Main install script
```

## Customization

### Machine-Specific Settings

Create `~/.dotfiles/local/.localrc` for machine-specific environment variables and settings:

```bash
# Example local configuration
export DEFAULT_USER=1
export GITHUB_TOKEN=your_token_here

# Custom paths
export PATH="/usr/local/custom/bin:$PATH"
```

### Git Configuration

Edit your name and email in `~/.dotfiles/packages/git/gitconfig`:

```ini
[user]
    name = Your Name
    email = your.email@example.com
```

Or set them in `~/.dotfiles/local/.localrc`:

```bash
git config --global user.name "Your Name"
git config --global user.email "your.email@example.com"
```

### Additional Tools

Add tool versions to `.tool-versions` for mise:

```
nodejs 20.11.0
python 3.12.1
ruby 3.3.0
```

### Custom Scripts

Add executable scripts to `bin/` directory - they'll automatically be in your PATH.

## Available Tasks

View all available tasks:

```bash
task -l
```

Common tasks:

```bash
task install          # Full system setup
task brew:install     # Install Homebrew packages
task symlink:install  # Symlink dotfiles
task mac:mac-defaults # Apply macOS defaults (macOS only)
```

## Troubleshooting

### Symlink Errors

If you get errors about existing files during symlinking:

```bash
# Backup existing config
mv ~/.zshrc ~/.zshrc.backup

# Re-run symlink task
task symlink:install
```

### Homebrew Issues

If Homebrew commands aren't found after installation:

```bash
# Add Homebrew to PATH (Apple Silicon)
eval "$(/opt/homebrew/bin/brew shellenv)"

# Add Homebrew to PATH (Intel)
eval "$(/usr/local/bin/brew shellenv)"
```

### Shell Changes Not Applied

After installation, restart your shell or source the config:

```bash
source ~/.zshrc
```

### Permission Issues

If you encounter permission errors:

```bash
# Fix ownership of dotfiles
sudo chown -R $(whoami) ~/.dotfiles

# Make scripts executable
chmod +x ~/.dotfiles/bin/*
chmod +x ~/.dotfiles/bootstrap.sh
chmod +x ~/.dotfiles/install
```

### Task Not Found

If `task` command isn't found:

```bash
# Install task manually
sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b ~/.local/bin
export PATH="$PATH:$HOME/.local/bin"
```

## Update

To update dotfiles:

```bash
cd ~/.dotfiles
git pull
task install
```

## Contributing

Feel free to fork this repository and customize it for your own use. If you find bugs or have suggestions, please open an issue.

## License

See [LICENSE](LICENSE) file for details.
