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

"""Tests for platform utilities."""

import pytest
import pytest_mock

from craft_application import util
from craft_application.util.platforms import (
    _ARCH_TRANSLATIONS_DEB_TO_PLATFORM,
    ENVIRONMENT_CRAFT_MANAGED_MODE,
)


@pytest.mark.parametrize("arch", _ARCH_TRANSLATIONS_DEB_TO_PLATFORM.keys())
def test_is_valid_architecture_true(arch):
    assert util.is_valid_architecture(arch)


def test_is_valid_architecture_false():
    assert not util.is_valid_architecture("unknown")


def test_get_hostname_returns_node_name(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch("platform.node", return_value="test-platform")
    assert util.get_hostname() == "test-platform"


def test_get_hostname_returns_unknown(mocker: pytest_mock.MockerFixture) -> None:
    mocker.patch("platform.node", return_value="")
    assert util.get_hostname() == "UNKNOWN"


@pytest.mark.parametrize("empty_hostname", ["", " ", "\n\t"])
def test_get_hostname_does_not_allow_empty(empty_hostname: str) -> None:
    assert util.get_hostname(empty_hostname) == "UNKNOWN"


@pytest.mark.parametrize("hostname", ["test-hostname", "another-hostname"])
def test_get_hostname_override(hostname: str) -> None:
    assert util.get_hostname(hostname) == hostname


def test_is_managed_is_false_if_env_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(ENVIRONMENT_CRAFT_MANAGED_MODE, raising=False)
    assert util.is_managed_mode() is False


@pytest.mark.parametrize(
    ("managed_mode_env", "expected"),
    [
        ("0", False),
        ("no", False),
        ("n", False),
        ("1", True),
        ("yes", True),
        ("y", True),
    ],
)
def test_is_managed_mode(
    monkeypatch: pytest.MonkeyPatch, managed_mode_env: str, *, expected: bool
) -> None:
    monkeypatch.setenv(ENVIRONMENT_CRAFT_MANAGED_MODE, managed_mode_env)
    assert util.is_managed_mode() is expected
