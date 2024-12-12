PROJECT=craft_application
ifneq ($(wildcard /etc/os-release),)
include /etc/os-release
export
endif

ifneq ($(VERSION_CODENAME),)
SETUP_TESTS_EXTRA_ARGS=--group apt-$(VERSION_CODENAME)
endif

UV_FROZEN=true

include common.mk

.PHONY: format
format: format-ruff format-codespell  ## Run all automatic formatters

.PHONY: lint
lint: lint-ruff lint-codespell lint-mypy lint-pyright lint-shellcheck lint-yaml lint-docs lint-twine  ## Run all linters

.PHONY: pack
pack: pack-pip  ## Build all packages

.PHONY: publish
publish: publish-pypi  ## Publish packages

.PHONY: publish-pypi
publish-pypi: clean package-pip lint-twine  ##- Publish Python packages to pypi
	uv tool run twine upload dist/*

# Used for installing build dependencies in CI.
.PHONY: install-build-deps
install-build-deps: install-lint-build-deps install-macos-build-deps install-linux-build-deps

# If additional build dependencies need installing in order to build the linting env.
.PHONY: install-lint-build-deps
install-lint-build-deps:

.PHONY: install-linux-build-deps
install-linux-build-deps:
ifneq ($(OS),Linux)
else ifeq ($(shell which apt-get),)
	$(warning apt-get not found. Please install dependencies yourself.)
else
	sudo $(APT) install skopeo
	# Needed for integration testing.
	sudo $(APT) install libyaml-dev python3-dev python3-pip python3-setuptools python3-venv python3-wheel
	# Needed for python-apt.
	sudo $(APT) install python-apt-dev libapt-pkg-dev clang
endif
ifneq ($(shell which snap),)
	sudo snap install lxd
endif
ifneq ($(shell which lxd),)
	sudo lxd init --auto
endif

.PHONY: install-macos-build-deps
install-macos-build-deps:
ifneq ($(OS),Darwin)
else ifeq ($(shell which brew),)
	$(warning brew not installed. Please install dependencies yourself.)
else
	brew install libgit2@1.7  # For building pygit2
	sudo cp -R /usr/local/opt/libgit2@1.7/* /usr/local
	brew install multipass
	brew install skopeo
endif
