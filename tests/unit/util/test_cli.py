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
"""Tests for cli functions."""
from unittest.mock import call, patch

import pytest
from craft_application.util import confirm_with_user


@pytest.fixture
def mock_isatty():
    with patch("sys.stdin.isatty", return_value=True) as mock_isatty:
        yield mock_isatty


@pytest.fixture
def mock_input():
    with patch("charmcraft.utils.cli.input", return_value="") as mock_input:
        yield mock_input


def test_confirm_with_user_defaults_with_tty(mock_input, mock_isatty):
    mock_input.return_value = ""
    mock_isatty.return_value = True

    assert confirm_with_user("prompt", default=True) is True
    assert mock_input.mock_calls == [call("prompt [Y/n]: ")]
    mock_input.reset_mock()

    assert confirm_with_user("prompt", default=False) is False
    assert mock_input.mock_calls == [call("prompt [y/N]: ")]


def test_confirm_with_user_defaults_without_tty(mock_input, mock_isatty):
    mock_isatty.return_value = False

    assert confirm_with_user("prompt", default=True) is True
    assert confirm_with_user("prompt", default=False) is False

    assert mock_input.mock_calls == []


@pytest.mark.parametrize(
    ("user_input", "expected"),
    [
        ("y", True),
        ("Y", True),
        ("yes", True),
        ("YES", True),
        ("n", False),
        ("N", False),
        ("no", False),
        ("NO", False),
    ],
)
def test_confirm_with_user(user_input, expected, mock_input, mock_isatty):
    mock_input.return_value = user_input

    assert confirm_with_user("prompt") == expected
    assert mock_input.mock_calls == [call("prompt [y/N]: ")]


def test_confirm_with_user_errors_in_managed_mode(
    mock_is_charmcraft_running_in_managed_mode,
):
    mock_is_charmcraft_running_in_managed_mode.return_value = True

    with pytest.raises(RuntimeError):
        confirm_with_user("prompt")


def test_confirm_with_user_pause_emitter(mock_isatty, emitter):
    """The emitter should be paused when using the terminal."""
    mock_isatty.return_value = True

    def fake_input(prompt):
        """Check if the Emitter is paused."""
        assert emitter.paused
        return ""

    with patch("charmcraft.utils.cli.input", fake_input):
        confirm_with_user("prompt")
