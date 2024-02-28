# This file is part of craft-application.
#
# Copyright 2024 Canonical Ltd.
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
"""Tests for internal str autilities."""

import pytest
from craft_application.util import string


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ("true", True),
        (" true", True),
        ("True", True),
        ("T", True),
        ("t", True),
        (" t ", True),
        ("yes", True),
        ("Yes", True),
        ("Y", True),
        ("y", True),
        ("  y  ", True),
        ("on", True),
        ("On", True),
        ("1", True),
        (" 1 ", True),
        ("false", False),
        ("False", False),
        ("  False", False),
        ("F", False),
        ("f", False),
        ("no", False),
        ("No", False),
        ("N", False),
        ("n", False),
        ("  n", False),
        ("off", False),
        ("Off", False),
        ("0", False),
        ("0  ", False),
    ],
)
def test_strtobool(data, expected):
    actual = string.strtobool(data)

    assert actual == expected


@pytest.mark.parametrize(
    ("data"),
    [
        (None),
        ({}),
        ([]),
        (""),
        (" "),
        ("invalid"),
        ("2"),
        ("-"),
        ("!"),
        ("*"),
        (b'yes'),
    ],
)
def test_strtobool_error(data):
    with pytest.raises((ValueError, TypeError), match="Invalid"):
        string.strtobool(data)
