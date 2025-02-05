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
"""Tests for prompt utilities."""

from contextlib import AbstractContextManager
from typing import cast
from unittest.mock import MagicMock

import pytest
import pytest_mock

from craft_application.errors import CraftError
from craft_application.util import prompt


@pytest.fixture
def prompting_context() -> MagicMock:
    return MagicMock()


def _patch_tty(mocker: pytest_mock.MockFixture, *, return_value) -> None:
    mocker.patch("sys.stdin.isatty", return_value=return_value)


@pytest.fixture
def fake_tty(mocker: pytest_mock.MockFixture) -> None:
    _patch_tty(mocker, return_value=True)


@pytest.fixture
def not_a_tty(mocker: pytest_mock.MockFixture) -> None:
    _patch_tty(mocker, return_value=False)


@pytest.fixture
def fake_input(mocker: pytest_mock.MockFixture) -> pytest_mock.MockType:
    return mocker.patch("builtins.input", return_value="test")


@pytest.fixture
def fake_getpass(mocker: pytest_mock.MockFixture) -> pytest_mock.MockType:
    return mocker.patch("getpass.getpass", return_value="fake-password")


def _get_prompting_context(
    prompting_context_mock: MagicMock,
) -> type[AbstractContextManager[None]]:
    return cast(type[AbstractContextManager[None]], prompting_context_mock)


@pytest.mark.usefixtures("fake_tty")
def test_prompting(
    prompting_context: MagicMock,
    fake_input: pytest_mock.MockType,
) -> None:
    """Test if prompting works properly."""
    prompt(
        "test prompt",
        prompting_context=_get_prompting_context(prompting_context),
    )
    fake_input.assert_called_with("test prompt")
    prompting_context.assert_called()
    prompting_context.return_value.__enter__.assert_called()
    prompting_context.return_value.__exit__.assert_called()


@pytest.mark.usefixtures("fake_tty")
def test_hidden_prompting(
    prompting_context: MagicMock,
    fake_getpass: pytest_mock.MockType,
) -> None:
    """Test if prompting works properly for hidden mode."""
    prompt(
        "test hidden prompt:",
        hide=True,
        prompting_context=_get_prompting_context(prompting_context),
    )
    fake_getpass.assert_called_with("test hidden prompt:")
    prompting_context.assert_called()
    prompting_context.return_value.__enter__.assert_called()
    prompting_context.return_value.__exit__.assert_called()


@pytest.mark.usefixtures("not_a_tty")
def test_raises_if_not_a_tty() -> None:
    """Test if prompting raises error if it is not a tty."""
    with pytest.raises(CraftError):
        prompt("prompt for craft error")


@pytest.mark.usefixtures("managed_mode")
def test_raises_in_managed_mode() -> None:
    """Test if prompting raises error if in managed mode."""
    with pytest.raises(RuntimeError):
        prompt("prompt for runtime error")
