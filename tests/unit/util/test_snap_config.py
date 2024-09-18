# This file is part of craft-application.
#
# Copyright 2022,2024 Canonical Ltd.
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

"""Unit tests for snap config model and helpers."""

from unittest.mock import MagicMock

import pytest
from craft_application.errors import CraftValidationError
from craft_application.util import SnapConfig, get_snap_config, is_running_from_snap
from snaphelpers import SnapCtlError


@pytest.fixture
def mock_config(mocker):
    return mocker.patch(
        "craft_application.util.snap_config.SnapConfigOptions", autospec=True
    )


@pytest.fixture
def mock_is_running_from_snap(mocker):
    return mocker.patch(
        "craft_application.util.snap_config.is_running_from_snap",
        return_value=True,
    )


@pytest.mark.parametrize(
    ("snap_name", "snap", "result"),
    [
        (None, None, False),
        (None, "/snap/testcraft/x1", False),
        ("testcraft", None, False),
        ("testcraft", "/snap/testcraft/x1", True),
        # test to avoid false positives
        ("my-snapped-terminal", "/snap/my-snapped-terminal/x1", False),
    ],
)
def test_is_running_from_snap(monkeypatch, snap_name, snap, result):
    """Test `is_running_from_snap()` function."""
    if snap_name is None:
        monkeypatch.delenv("SNAP_NAME", raising=False)
    else:
        monkeypatch.setenv("SNAP_NAME", snap_name)

    if snap is None:
        monkeypatch.delenv("SNAP", raising=False)
    else:
        monkeypatch.setenv("SNAP", snap)

    assert is_running_from_snap(app_name="testcraft") == result


def test_unmarshal():
    """Verify unmarshalling works as expected."""
    config = SnapConfig.unmarshal({"provider": "lxd"})

    assert config.provider == "lxd"


def test_unmarshal_not_a_dictionary():
    """Verify unmarshalling with data that is not a dictionary raises an error."""
    with pytest.raises(TypeError) as raised:
        SnapConfig.unmarshal("provider=lxd")  # pyright: ignore[reportArgumentType]

    assert str(raised.value) == "snap config data is not a dictionary"


def test_unmarshal_invalid_provider_error():
    """Verify unmarshalling with an invalid provider raises an error."""
    with pytest.raises(CraftValidationError) as raised:
        SnapConfig.unmarshal({"provider": "invalid-value"})

    assert str(raised.value) == (
        "Bad snap config content:\n"
        "- input should be 'lxd' or 'multipass' (in field 'provider')"
    )


def test_unmarshal_extra_data_error():
    """Verify unmarshalling with extra data raises an error."""
    with pytest.raises(CraftValidationError) as raised:
        SnapConfig.unmarshal({"provider": "lxd", "test": "test"})

    assert str(raised.value) == (
        "Bad snap config content:\n"
        "- extra inputs are not permitted (in field 'test')"
    )


@pytest.mark.parametrize("provider", ["lxd", "multipass"])
@pytest.mark.usefixtures("mock_is_running_from_snap")
def test_get_snap_config(mock_config, provider):
    """Verify getting a valid snap config."""

    def fake_as_dict():
        return {"provider": provider}

    mock_config.return_value.as_dict.side_effect = fake_as_dict
    config = get_snap_config(app_name="testcraft")

    assert config == SnapConfig(provider=provider)


@pytest.mark.usefixtures("mock_is_running_from_snap")
def test_get_snap_config_empty(mock_config):
    """Verify getting an empty config returns a default SnapConfig."""

    def fake_as_dict():
        return {}

    mock_config.return_value.as_dict.side_effect = fake_as_dict
    config = get_snap_config(app_name="testcraft")

    assert config == SnapConfig()


def test_get_snap_config_not_from_snap(mock_is_running_from_snap):
    """Verify None is returned when snapcraft is not running from a snap."""
    mock_is_running_from_snap.return_value = False

    assert get_snap_config(app_name="testcraft") is None


@pytest.mark.parametrize("error", [AttributeError, SnapCtlError(process=MagicMock())])
@pytest.mark.usefixtures("mock_is_running_from_snap")
def test_get_snap_config_handle_init_error(error, mock_config):
    """An error when initializing the snap config object should return None."""
    mock_config.side_effect = error

    assert get_snap_config(app_name="testcraft") is None


@pytest.mark.parametrize("error", [AttributeError, SnapCtlError(process=MagicMock())])
@pytest.mark.usefixtures("mock_is_running_from_snap")
def test_get_snap_config_handle_fetch_error(error, mock_config):
    """An error when fetching the snap config should return None."""
    mock_config.return_value.fetch.side_effect = error

    assert get_snap_config(app_name="testcraft") is None
