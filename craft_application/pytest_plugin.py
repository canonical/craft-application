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
"""A pytest plugin for assisting in testing apps that use craft-application."""

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def debug_mode() -> None:
    """Ensure that the application is in debug mode, raising exceptions from run().

    This fixture is automatically used. To disable debug mode for specific tests that
    require it, use the :py:func:`production_mode` fixture.
    """
    os.environ["CRAFT_DEBUG"] = "1"


@pytest.fixture
def production_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Put the application into production mode.

    This fixture puts the application into production mode rather than debug mode.
    It should only be used if the application needs to test behaviour that differs
    between debug mode and production mode.
    """
    monkeypatch.setenv("CRAFT_DEBUG", "0")
