# This file is part of craft_application.
#
# Copyright 2025 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Witchcraft is a fake craft application used for e2e testing of craft-application.

This version uses many non-default features and is intended to test unusual
configurations.
"""

try:
    # Since testcraft is never packaged, a "_version" module is never generated
    # by setuptools_scm. Thus, the import is ignored here. Normal Craft applications
    # should not have to do this.
    from ._version import __version__  # type: ignore[reportMissingImports, import-untyped, import-not-found]
except ImportError:  # pragma: no cover
    from importlib.metadata import PackageNotFoundError, version

    try:
        __version__ = version("witchcraft")
    except PackageNotFoundError:
        __version__ = "dev"
