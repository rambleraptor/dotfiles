#!/bin/bash
#
# bootstrap.sh
# Bootstrap script for setting up a new machine with dotfiles
#

set -e

DOTFILES_DIR="$HOME/.dotfiles"
DOTFILES_REPO="https://github.com/rambleraptor/dotfiles.git"

echo "🚀 Bootstrapping dotfiles setup..."

# Check if running on macOS or Linux
if [[ "$OSTYPE" == "darwin"* ]]; then
  OS="macos"
  echo "✓ Detected macOS"
elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
  OS="linux"
  echo "✓ Detected Linux"
else
  echo "❌ Unsupported operating system: $OSTYPE"
  exit 1
fi

# Install Homebrew if on macOS and not installed
if [[ "$OS" == "macos" ]] && ! command -v brew &> /dev/null; then
  echo "📦 Installing Homebrew..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
fi

# Clone dotfiles repository if not already present
if [[ ! -d "$DOTFILES_DIR" ]]; then
  echo "📥 Cloning dotfiles repository..."
  git clone "$DOTFILES_REPO" "$DOTFILES_DIR"
  cd "$DOTFILES_DIR"
else
  echo "✓ Dotfiles directory already exists"
  cd "$DOTFILES_DIR"

  # Update repository
  echo "🔄 Updating dotfiles repository..."
  git pull origin main 2>/dev/null || git pull origin master 2>/dev/null || echo "⚠️  Could not pull latest changes"
fi

# Install task if not already installed
if ! command -v task &> /dev/null; then
  echo "📦 Installing go-task..."
  if [[ "$OS" == "macos" ]]; then
    brew install go-task
  else
    # Install task on Linux
    sh -c "$(curl --location https://taskfile.dev/install.sh)" -- -d -b ~/.local/bin
    export PATH="$PATH:$HOME/.local/bin"
  fi
fi

# Run the main install task
echo "⚙️  Running installation tasks..."
task install

echo ""
echo "✅ Bootstrap complete!"
echo ""
echo "Next steps:"
echo "  1. Restart your shell or run: source ~/.zshrc"
echo "  2. Review and customize ~/.dotfiles/local/.localrc for machine-specific settings"
echo "  3. Set up your Git credentials if needed"
echo ""
