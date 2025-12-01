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
from craft_application.util import (
    SnapConfig,
    get_snap_base,
    get_snap_config,
    is_running_from_snap,
)
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
        "- input should be 'lxd' or 'multipass' (in field 'provider', input: 'invalid-value')"
    )


def test_unmarshal_extra_data_error():
    """Verify unmarshalling with extra data raises an error."""
    with pytest.raises(CraftValidationError) as raised:
        SnapConfig.unmarshal({"provider": "lxd", "test": "test"})

    assert str(raised.value) == (
        "Bad snap config content:\n- extra inputs are not permitted (in field 'test', input: 'test')"
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


@pytest.mark.parametrize(
    ("snap_yaml_content", "expected_base"),
    [
        pytest.param(
            # Simple snap with core24
            "name: testcraft\nbase: core24\nversion: 1.0\n",
            "core24",
            id="core24",
        ),
        pytest.param(
            # Snap with core22 (common in 22.04 snaps)
            "name: my-snap\nbase: core22\nversion: 2.0\nsummary: A test snap\n",
            "core22",
            id="core22",
        ),
        pytest.param(
            # Snap with core20
            "name: hello-world\nversion: 6.4\nsummary: Hello world example\nbase: core20\n",
            "core20",
            id="core20",
        ),
        pytest.param(
            # More complex snap.yaml similar to real snaps like snapcraft
            """name: test-app
version: '8.0'
summary: Test application
description: |
  A test application for craft-application
base: core24
grade: stable
confinement: classic
""",
            "core24",
            id="complex-snap",
        ),
    ],
)
def test_get_snap_base_success(tmp_path, monkeypatch, snap_yaml_content, expected_base):
    """Test get_snap_base returns the correct base from various snap.yaml formats."""
    # Set up environment
    monkeypatch.setenv("SNAP_NAME", "testcraft")
    monkeypatch.setenv("SNAP", str(tmp_path))

    # Create snap.yaml with base
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()
    snap_yaml = meta_dir / "snap.yaml"
    snap_yaml.write_text(snap_yaml_content)

    assert get_snap_base("testcraft") == expected_base


def test_get_snap_base_not_from_snap(monkeypatch):
    """Test get_snap_base returns None when not running from snap."""
    monkeypatch.delenv("SNAP_NAME", raising=False)
    monkeypatch.delenv("SNAP", raising=False)

    assert get_snap_base("testcraft") is None


@pytest.mark.parametrize(
    ("setup_snap_env", "create_yaml", "yaml_content", "reason"),
    [
        pytest.param(
            False,
            False,
            None,
            "SNAP env var not set",
            id="no-snap-env",
        ),
        pytest.param(
            True,
            False,
            None,
            "snap.yaml doesn't exist",
            id="no-yaml",
        ),
        pytest.param(
            True,
            True,
            "name: testcraft\nversion: 1.0\n",
            "no base in snap.yaml",
            id="no-base",
        ),
    ],
)
def test_get_snap_base_returns_none(
    tmp_path, monkeypatch, setup_snap_env, create_yaml, yaml_content, reason
):
    """Test get_snap_base returns None in various scenarios."""
    monkeypatch.setenv("SNAP_NAME", "testcraft")

    if setup_snap_env:
        monkeypatch.setenv("SNAP", str(tmp_path))
    else:
        monkeypatch.delenv("SNAP", raising=False)

    if create_yaml:
        meta_dir = tmp_path / "meta"
        meta_dir.mkdir()
        snap_yaml = meta_dir / "snap.yaml"
        snap_yaml.write_text(yaml_content)

    assert get_snap_base("testcraft") is None, f"Should return None when {reason}"


def test_get_snap_base_invalid_yaml(tmp_path, monkeypatch):
    """Test get_snap_base returns None when snap.yaml is invalid."""
    monkeypatch.setenv("SNAP_NAME", "testcraft")
    monkeypatch.setenv("SNAP", str(tmp_path))

    # Create invalid snap.yaml
    meta_dir = tmp_path / "meta"
    meta_dir.mkdir()
    snap_yaml = meta_dir / "snap.yaml"
    snap_yaml.write_text("invalid: yaml: content: [")

    assert get_snap_base("testcraft") is None
