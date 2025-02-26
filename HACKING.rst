*****************
Craft-Application
*****************

Welcome to Craft-Application! We hope this document helps you get started. Before contributing any code, please sign the `Canonical contributor licence agreement`_.

Setting up a development environment
------------------------------------
We use a forking, feature-based workflow, so you should start by forking the repository. Once you've done that, clone the project to your computer using git clone's ``--recurse-submodules`` parameter. (See more on the `git submodules`_ documentation.)

Dependencies
============

Dependencies will generally be installed upon running ``make setup``, though in some
environments there may be further manual steps. If you don't have ``snap`` available,
please install `uv`_.

Initial Setup
#############

After cloning the repository but before making any changes, it's worth ensuring that the tests, linting and tools all run on your machine::

    make setup
    make lint
    make test

While the use of pre-commit_ is optional, it is highly encouraged, as it runs automatic fixes for files when `git commit` is called, including code formatting with ``ruff``.  The versions available in ``apt`` from Debian 11 (bullseye), Ubuntu 22.04 (jammy) and newer are sufficient, but you can also install the latest with ``pip install pre-commit``. Once you've installed it, run ``pre-commit install`` in this git repository to install the pre-commit hooks.

.. _`Canonical contributor licence agreement`: http://www.ubuntu.com/legal/contributors/
.. _deadsnakes: https://launchpad.net/~deadsnakes/+archive/ubuntu/ppa
.. _`git submodules`: https://git-scm.com/book/en/v2/Git-Tools-Submodules#_cloning_submodules
.. _pre-commit: https://pre-commit.com/
.. _pyproject.toml: ./pyproject.toml
.. _Pyright: https://github.com/microsoft/pyright
.. _pytest: https://pytest.org
.. _ruff: https://github.com/astral-sh/ruff
.. _ShellCheck: https://www.shellcheck.net/
.. _uv: https://docs.astral.sh/uv/
