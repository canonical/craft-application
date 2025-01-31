PROJECT=craft_application
UV_TEST_GROUPS := "--group=dev"
UV_DOCS_GROUPS := "--group=docs"
UV_LINT_GROUPS := "--group=lint" "--group=types"

# If you have dev dependencies that depend on your distro version, uncomment these:
ifneq ($(wildcard /etc/os-release),)
include /etc/os-release
endif
ifdef VERSION_CODENAME
UV_TEST_GROUPS += "--group=dev-$(VERSION_CODENAME)"
UV_DOCS_GROUPS += "--group=dev-$(VERSION_CODENAME)"
UV_LINT_GROUPS += "--group=dev-$(VERSION_CODENAME)"
endif

include common.mk

.PHONY: format
format: format-ruff format-codespell format-prettier  ## Run all automatic formatters

.PHONY: lint
lint: lint-ruff lint-codespell lint-mypy lint-prettier lint-pyright lint-shellcheck lint-docs lint-twine  ## Run all linters

.PHONY: pack
pack: pack-pip  ## Build all packages

.PHONY: publish
publish: publish-pypi  ## Publish packages

.PHONY: publish-pypi
publish-pypi: clean pack-pip lint-twine  ##- Publish Python packages to pypi
	uv tool run twine upload dist/*

# Find dependencies that need installing
APT_PACKAGES :=
ifeq ($(wildcard /usr/include/libxml2/libxml/xpath.h),)
APT_PACKAGES += libxml2-dev
endif
ifeq ($(wildcard /usr/include/libxslt/xslt.h),)
APT_PACKAGES += libxslt1-dev
endif
ifeq ($(wildcard /usr/share/doc/python3-venv/copyright),)
APT_PACKAGES += python3-venv
endif
ifeq ($(wildcard /usr/share/doc/libapt-pkg-dev/copyright),)
APT_PACKAGES += libapt-pkg-dev
endif
ifeq ($(wildcard /usr/share/doc/libgit2-dev/copyright),)
APT_PACKAGES += libgit2-dev
endif
ifeq ($(wildcard /usr/share/doc/fuse-overlayfs/copyright),)
APT_PACKAGES += fuse-overlayfs
endif


# Used for installing build dependencies in CI.
.PHONY: install-build-deps
install-build-deps: install-lint-build-deps install-fetch-service install-lxd
ifeq ($(APT_PACKAGES),)
else ifeq ($(shell which apt-get),)
	$(warning Cannot install build dependencies without apt.)
	$(warning Please ensure the equivalents to these packages are installed: $(APT_PACKAGES))
else
	sudo $(APT) install $(APT_PACKAGES)
endif

# If additional build dependencies need installing in order to build the linting env.
.PHONY: install-lint-build-deps
install-lint-build-deps:

.PHONY: install-fetch-service
install-fetch-service:
ifneq ($(shell which fetch-service),)
else ifneq ($(shell which snap),)
	sudo snap install fetch-service --beta
else
	$(warning Fetch service not installed. Please install it yourself.)
endif

.PHONY: install-lxd
install-lxd:
ifneq ($(shell which lxd),)
else ifneq ($(shell which snap),)
	sudo snap install lxd --beta
	sudo lxd init --minimal
else
	$(warning LXD not installed. Please install it yourself.)
endif
ifdef CI  # Always init lxd in CI
	sudo lxd init --minimal
endif
