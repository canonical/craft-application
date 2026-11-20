# This file is part of craft-application.
#
# Copyright 2026 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for the selection and loading of the environment."""

import pytest
from craft_application.services.sourcestore._environment import (
    _PRODUCTION,
    _STAGING,
    SdEnvironment,
    get_sd_environment,
)
from craft_cli import CraftError

fake_environment = SdEnvironment(
    api_url="https://api.example.com",
    dashboard_url="https://dashboard.example.com",
    git_url="https://git.example.com",
    login_url="https://login.example.com",
    source_store_credentials=None,
    upstream_plane="ubuntu/dummy",
    push_plane=None,
    source_store_gateway="https://store.example.com",
    publisher_gateway_url="https://gw.example.com",
)


@pytest.fixture(autouse=True)
def clear_lru() -> None:
    """Clear the LRU between test runs to get a new calculation each time."""
    get_sd_environment.cache_clear()


@pytest.mark.parametrize(
    ("env", "expected"),
    [
        pytest.param(None, _STAGING, id="default"),
        pytest.param("STAGING", _STAGING, id="staging"),
        pytest.param("PROD", _PRODUCTION, id="prod"),
        pytest.param("PRODUCTION", _PRODUCTION, id="production"),
        pytest.param(
            fake_environment.model_dump_json(), fake_environment, id="from_json"
        ),
    ],
)
def test_get_sd_environment(
    monkeypatch: pytest.MonkeyPatch, env: str, expected: SdEnvironment
) -> None:
    monkeypatch.delenv("CRAFT_SD_ENV", raising=False)
    if env:
        monkeypatch.setenv("CRAFT_SD_ENV", env)

    assert get_sd_environment() == expected


def test_get_sd_environment_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CRAFT_SD_ENV", fake_environment.model_dump_json())
    monkeypatch.setenv("CRAFT_API_URL", "https://api-v2.example.com")
    monkeypatch.setenv("CRAFT_SOURCE_STORE_CREDENTIALS", "encoded-credentials")

    env = get_sd_environment()

    # Ensure that only the overridden values were changed
    assert env.api_url == "https://api-v2.example.com"
    assert env.source_store_credentials == "encoded-credentials"
    for name, val in env:
        if name in {"api_url", "source_store_credentials"}:
            continue

        assert val == getattr(fake_environment, name)


@pytest.mark.parametrize(
    ("bad_value"),
    [
        pytest.param("CABBAGE", id="bad-str"),
        pytest.param('{"marco": "polo"}', id="bad-json"),
    ],
)
def test_get_sd_environment_bad_value(
    monkeypatch: pytest.MonkeyPatch, bad_value: str
) -> None:
    monkeypatch.setenv("CRAFT_SD_ENV", bad_value)

    with pytest.raises(CraftError, match="Invalid value for CRAFT_SD_ENV"):
        get_sd_environment()
