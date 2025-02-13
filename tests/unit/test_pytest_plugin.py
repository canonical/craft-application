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
"""Simple tests for the pytest plugin."""

import os

import pytest


def test_sets_debug_mode():
    assert os.getenv("CRAFT_DEBUG") == "1"


@pytest.mark.usefixtures("production_mode")
def test_production_mode_sets_production_mode():
    assert os.getenv("CRAFT_DEBUG") == "0"
