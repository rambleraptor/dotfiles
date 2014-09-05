if test ! $(which brew)
then
      echo "  Installing Homebrew for you."
        ruby -e "$(curl -fsSL https://raw.github.com/Homebrew/homebrew/go/install)" > /tmp/homebrew-install.log
fi

# Install everything in the brewfile
brew bundle
