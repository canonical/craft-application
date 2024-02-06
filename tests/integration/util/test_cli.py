# Copyright 2024 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import string
from unittest import mock

import pytest
from craft_application.util.cli import read_bool


@pytest.fixture()
def mock_input(monkeypatch, user_input):
    if not isinstance(user_input, list):
        user_input = [user_input]
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    mock_input = mock.Mock(spec_set=input, side_effect=user_input)
    monkeypatch.setattr("builtins.input", mock_input)
    return mock_input


@pytest.mark.parametrize("default", [True, False, None])
def test_read_bool_no_tty(mocker, default):
    mocker.patch("sys.stdin.isatty", return_value=False)
    mock_input = mocker.patch("builtins.input")

    assert read_bool("any prompt", default=default) == default

    mock_input.assert_not_called()


@pytest.mark.parametrize("user_input", "y")
@pytest.mark.parametrize(
    ("prompt", "default", "full_prompt"),
    [
        ("Eh?", True, "Eh? [Y/n]: "),
        ("Hmm", False, "Hmm [y/N]: "),
        ("So...", None, "So... [y/n]: "),
    ],
)
def test_read_bool_correct_prompt(mock_input, prompt, default, full_prompt):
    assert read_bool(prompt, default)

    mock_input.assert_called_once_with(full_prompt)


@pytest.mark.parametrize(
    ("user_input", "expected"),
    [
        ("y", True),
        ("Yeppers", True),
        ("n", False),
        ("NOOOOO!", False),
    ],
)
def test_read_bool_explicit_input(mock_input, expected):
    assert read_bool("question", default=None) == expected


@pytest.mark.parametrize("default", [True, False])
@pytest.mark.parametrize("user_input", ["", " ", "\n", string.whitespace])
def test_read_bool_no_input(mock_input, default):
    assert read_bool("some prompt", default=default) == default


@pytest.mark.parametrize(
    ("user_input", "default", "expected"),
    [
        (["blah", "abc", "y"], None, True),
        (["blah", "abc", "n"], None, False),
        (["", "n"], None, False),
        (["", "y"], None, True),
        (["argh", ""], False, False),
        (["argh", ""], True, True),
    ],
)
def test_read_bool_multiple_times(mock_input, user_input, default, expected):
    assert read_bool("some prompt", default=default) == expected

    assert mock_input.call_count == len(user_input)
