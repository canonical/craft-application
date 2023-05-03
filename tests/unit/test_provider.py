#  This file is part of craft-application.
#
#  Copyright 2023 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Provider manager tests."""
import re
import sys
from typing import cast
from unittest import mock

import pytest
from craft_application import ProviderManager, utils
from craft_application.errors import CraftEnvironmentError
from craft_cli import CraftError
from craft_providers.lxd import LXDProvider
from craft_providers.multipass import MultipassProvider


@pytest.fixture
def provider_manager():
    yield ProviderManager("test_app")


@pytest.mark.parametrize(
    [
        "app_name",
        "managed_mode_env",
        "expected_managed_mode_env",
        "provider_env",
        "expected_provider_env",
    ],
    [
        ("test_app", "ABCXYZ", "ABCXYZ", "ZYXCBA", "ZYXCBA"),
        (
            "test_app",
            None,
            "TEST_APP_MANAGED_MODE",
            None,
            "TEST_APP_PROVIDER",
        ),
    ],
)
def test_init_params(
    check,
    app_name,
    managed_mode_env,
    expected_managed_mode_env,
    provider_env,
    expected_provider_env,
):
    manager = ProviderManager(
        app_name, managed_mode_env=managed_mode_env, provider_env=provider_env
    )

    check.equal(manager.managed_mode_env, expected_managed_mode_env)
    check.equal(manager.provider_env, expected_provider_env)


# region get_provider tests
def test_get_provider_managed(monkeypatch, provider_manager):
    monkeypatch.setenv(provider_manager.managed_mode_env, "1")

    with pytest.raises(CraftError) as exc_info:
        provider_manager.get_provider()

    assert exc_info.value.args[0] == "Cannot nest managed environments."


@pytest.mark.parametrize("provider", ["invalid", ""])
def test_get_provider_invalid_provider_env(
    check, monkeypatch, provider_manager, provider
):
    monkeypatch.setenv(provider_manager.provider_env, provider)

    with pytest.raises(CraftEnvironmentError) as exc_info:
        provider_manager.get_provider()

    check.is_in("Valid values: lxd, multipass", exc_info.value.details)
    check.equal("Unset variable or fix value.", exc_info.value.resolution)


@pytest.mark.parametrize(
    ["platform", "provider_class"],
    [
        pytest.param("linux", LXDProvider, id="linux"),
        pytest.param("darwin", MultipassProvider, id="macos"),
        pytest.param("win32", MultipassProvider, id="windows"),
        pytest.param("unknown", MultipassProvider, id="platform_unkown"),
    ],
)
def test_get_provider_default_correct_class(
    monkeypatch, provider_manager, platform, provider_class
):
    monkeypatch.delenv(provider_manager.provider_env, raising=False)
    monkeypatch.setattr(sys, "platform", platform)

    provider = provider_manager.get_provider()

    assert isinstance(provider, provider_class)


@pytest.mark.parametrize(
    ["provider_name", "provider_class"],
    [
        ("lxd", LXDProvider),
        ("multipass", MultipassProvider),
    ],
)
def test_get_provider_not_installed(
    check, monkeypatch, provider_manager, provider_name, provider_class
):
    monkeypatch.setenv(provider_manager.provider_env, provider_name)
    mock_returns_false = mock.Mock(return_value=False)
    monkeypatch.setattr(provider_class, "is_provider_installed", mock_returns_false)
    monkeypatch.setattr(utils, "confirm_with_user", mock_returns_false)

    with pytest.raises(CraftError) as exc_info:
        provider_manager.get_provider()

    resolution = cast(str, exc_info.value.resolution)
    check.is_true(re.match(r"Install [a-z]+ and run again.", resolution))
    check.is_in(provider_name, exc_info.value.resolution)
    message = cast(str, exc_info.value.args[0])
    check.is_true(re.match(r"Cannot proceed without [a-z]+ installed", message))
    check.is_in(provider_name, exc_info.value.args[0])


@pytest.mark.parametrize(
    ["provider_name", "provider_class"],
    [
        ("lxd", LXDProvider),
        ("multipass", MultipassProvider),
    ],
)
def test_get_provider_auto_install(
    check, monkeypatch, provider_manager, provider_name, provider_class
):
    monkeypatch.setenv(provider_manager.provider_env, provider_name)
    mock_provider_installed = mock.Mock(return_value=False)
    mock_ensure_available = mock.Mock()
    mock_confirm = mock.Mock(return_value=True)
    monkeypatch.setattr(
        provider_class, "is_provider_installed", mock_provider_installed
    )
    monkeypatch.setattr(
        provider_class, "ensure_provider_is_available", mock_ensure_available
    )
    monkeypatch.setattr(utils, "confirm_with_user", mock_confirm)

    provider = provider_manager.get_provider()

    assert isinstance(provider, provider_class)


# endregion
