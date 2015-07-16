#!/usr/bin/env bash

source $DOTFILES/bootstrap/lib.sh
# OSX Defaults
# Mostly stolen from https://mths.be/osx

#######################################
# General UI stuff
#######################################

action "Use AirDrop over every interface. srsly this should be a default."
defaults write com.apple.NetworkBrowser BrowseAllInterfaces 1

action "Expand save panel by default"
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode -bool true
defaults write NSGlobalDomain NSNavPanelExpandedStateForSaveMode2 -bool true

action "Expand print panel by default"
defaults write NSGlobalDomain PMPrintingExpandedStateForPrint -bool true
defaults write NSGlobalDomain PMPrintingExpandedStateForPrint2 -bool true

action "Save to disk (not to iCloud) by default"
defaults write NSGlobalDomain NSDocumentSaveNewDocumentsToCloud -bool false

action "Automatically quit printer app once the print jobs complete"
defaults write com.apple.print.PrintingPrefs "Quit When Finished" -bool true

action "Disable the “Are you sure you want to open this application?” dialog"
defaults write com.apple.LaunchServices LSQuarantine -bool false

action "Remove duplicates in the Open With menu (also see `lscleanup` alias)"
/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister -kill -r -domain local -domain system -domain user

#######################################
# Trackpad, keyboard
#######################################

action "Set a blazingly fast keyboard repeat rate"
defaults write NSGlobalDomain KeyRepeat -int 0

#######################################
# Finder
#######################################

action "When performing a search, search the current folder by default"
defaults write com.apple.finder FXDefaultSearchScope -string "SCcf"

action "Disable the warning when changing a file extension"
defaults write com.apple.finder FXEnableExtensionChangeWarning -bool false

action "Avoid creating .DS_Store files on network volumes"
defaults write com.apple.desktopservices DSDontWriteNetworkStores -bool true

action "Show the ~/Library folder"
chflags nohidden ~/Library

#######################################
# Mail
#######################################

action "Copy email addresses as foo@example.com instead of Foo Bar <foo@example.com> in Mail.app"
defaults write com.apple.mail AddressesIncludeNameOnPasteboard -bool false

#######################################
# Transmission
#######################################

action "Use `~/Documents/Torrents` to store incomplete downloads"
defaults write org.m0k.transmission UseIncompleteDownloadFolder -bool true
defaults write org.m0k.transmission IncompleteDownloadFolder -string "${HOME}/Documents/Torrents"

action "Don’t prompt for confirmation before downloading"
defaults write org.m0k.transmission DownloadAsk -bool false

action "Trash original torrent files"
defaults write org.m0k.transmission DeleteOriginalTorrent -bool true

action "Hide the donate message"
defaults write org.m0k.transmission WarningDonate -bool false
action "Hide the legal disclaimer"
defaults write org.m0k.transmission WarningLegal -bool false

#######################################
# Kill all apps
#######################################

for app in "Activity Monitor" "Address Book" "Calendar" "Contacts" "cfprefsd" \
        "Dock" "Finder" "Mail" "Messages" "Safari" "SizeUp" "SystemUIServer" \
            "Terminal" "Transmission" "Twitter" "iCal"; do
    killall "${app}" > /dev/null 2>&1
done
ok "Done. Note that some of these changes require a logout/restart to take effect."
