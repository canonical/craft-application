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
        (b"yes"),
    ],
)
def test_strtobool_error(data):
    with pytest.raises((ValueError, TypeError), match="Invalid"):
        string.strtobool(data)


#################
# Humanize List #
#################


@pytest.mark.parametrize(
    ("items", "conjunction", "expected"),
    [
        ([], "and", ""),
        (["foo"], "and", "'foo'"),
        (["foo", "bar"], "and", "'bar' and 'foo'"),
        (["foo", "bar", "baz"], "and", "'bar', 'baz', and 'foo'"),
        (["foo", "bar", "baz", "qux"], "and", "'bar', 'baz', 'foo', and 'qux'"),
        ([], "or", ""),
        (["foo"], "or", "'foo'"),
        (["foo", "bar"], "or", "'bar' or 'foo'"),
        (["foo", "bar", "baz"], "or", "'bar', 'baz', or 'foo'"),
        (["foo", "bar", "baz", "qux"], "or", "'bar', 'baz', 'foo', or 'qux'"),
    ],
)
def test_humanize_list(items, conjunction, expected):
    """Test humanize_list."""
    assert string.humanize_list(items, conjunction) == expected


def test_humanize_list_sorted():
    """Verify `sort` parameter."""
    input_list = ["z", "a", "m test", "1"]

    # unsorted list is in the same order as the original list
    expected_list_unsorted = "'z', 'a', 'm test', and '1'"

    # sorted list is sorted alphanumerically
    expected_list_sorted = "'1', 'a', 'm test', and 'z'"

    assert string.humanize_list(input_list, "and") == expected_list_sorted
    assert string.humanize_list(input_list, "and", sort=True) == expected_list_sorted
    assert string.humanize_list(input_list, "and", sort=False) == expected_list_unsorted
