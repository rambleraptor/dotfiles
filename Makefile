SHELL := /bin/bash

all:
	./bootstrap.sh
	pip install -r Pipfile
	brew tab homebrew/boneyard
	brew bundle
