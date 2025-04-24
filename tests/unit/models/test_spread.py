# This file is part of craft-application.
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
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Unit tests for spread models."""

import pytest

from craft_application.models.spread import SpreadBackend, SpreadSystem


@pytest.mark.parametrize(
    ("systems", "expected"),
    [
        (["ubuntu-24.04-64"], ["ubuntu-24.04-64"]),
        ([{"ubuntu-24.04-64": None}], [{"ubuntu-24.04-64": SpreadSystem(workers=1)}]),
        (
            ["ubuntu-24.04-64", {"ubuntu-24.04-64": None}],
            ["ubuntu-24.04-64", {"ubuntu-24.04-64": SpreadSystem(workers=1)}],
        ),
    ],
)
def test_systems_from_craft(systems, expected):
    assert SpreadBackend.systems_from_craft(systems) == expected
