#  This file is part of craft-application.
#
#  Copyright 2025 Canonical Ltd.
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
"""Unit tests for the state service."""

import os
import pathlib
import re
from collections.abc import Callable

import pytest
from craft_application import _const, errors
from craft_application.services import StateService, state


@pytest.fixture
def state_service_factory(app_metadata, fake_services) -> Callable[[], StateService]:
    """A factory for creating a state service."""

    def _get_service():
        """Return an instance of the StateService."""
        return state.StateService(app_metadata, fake_services)

    return _get_service


@pytest.fixture
def state_dir(monkeypatch, tmp_path) -> pathlib.Path:
    """Ensure CRAFT_STATE_DIR is set to a temporary directory."""
    state_dir = (tmp_path / "state").resolve()
    monkeypatch.setenv(_const.CRAFT_STATE_DIR_ENV, str(state_dir))
    return state_dir


@pytest.fixture
def no_state_dir_env_var(monkeypatch) -> None:
    """Ensure CRAFT_STATE_DIR is not set."""
    monkeypatch.delenv(_const.CRAFT_STATE_DIR_ENV, raising=False)


##############################
# State dir management tests #
##############################


def test_state_dir(state_service_factory, state_dir, mocker, emitter):
    """Create and destroy the state dir in manager mode."""
    mock_register = mocker.patch("atexit.register")

    state_service = state_service_factory()

    # create the state directory in manager mode
    assert state_dir.exists()
    mock_register.assert_called_once_with(state_service._destroy_state_dir)
    emitter.assert_debug("Getting state directory from CRAFT_STATE_DIR.")
    emitter.assert_debug(f"Using {str(state_dir)!r} for the state directory.")


@pytest.mark.usefixtures("managed_mode")
def test_state_dir_managed_mode(
    state_service_factory, mocker, monkeypatch, state_dir, emitter
):
    """Don't create or destroy the state directory in managed mode."""
    monkeypatch.setenv(_const.CRAFT_STATE_DIR_ENV, str(state_dir))
    mock_register = mocker.patch("atexit.register")

    state_service_factory()

    # don't create the state directory in managed mode
    assert not state_dir.exists()
    mock_register.assert_not_called()
    emitter.assert_debug("Getting state directory from CRAFT_STATE_DIR.")
    emitter.assert_debug(f"Using {str(state_dir)!r} for the state directory.")
    emitter.assert_debug("Not managing state directory in managed mode.")


@pytest.mark.usefixtures("managed_mode", "no_state_dir_env_var")
def test_state_dir_managed_mode_error(state_service_factory):
    """Error if CRAFT_STATE_DIR isn't set in managed mode."""
    expected_error = re.escape(
        "Couldn't get state directory from CRAFT_STATE_DIR in managed mode."
    )

    with pytest.raises(errors.StateServiceError, match=expected_error):
        state_service_factory()


@pytest.mark.usefixtures("no_state_dir_env_var")
def test_state_dir_xdg(state_service_factory, monkeypatch, tmp_path, emitter):
    """Create the state dir from XDG_RUNTIME_DIR."""
    state_dir = (tmp_path / "xdg_runtime" / str(os.getpid())).resolve()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(state_dir.parent))

    state_service_factory()

    # create the state directory in user mode
    assert state_dir.exists()
    emitter.assert_debug("Getting state directory from XDG_RUNTIME_DIR.")
    emitter.assert_debug(f"Using {str(state_dir)!r} for the state directory.")


@pytest.mark.usefixtures("no_state_dir_env_var")
def test_state_dir_xdg_error(state_service_factory, mocker, tmp_path, emitter):
    """Fallback to a temp home directory if the xdg dir fails."""
    state_dir = (tmp_path / "state").resolve()
    mocker.patch(
        "craft_application.services.state.BaseDirectory.get_runtime_dir",
        side_effect=KeyError(),
    )
    mocker.patch(
        "craft_application.util.get_home_temporary_directory", return_value=state_dir
    )

    state_service_factory()

    # create the state directory in user mode
    assert state_dir.exists()
    emitter.assert_debug("Couldn't get XDG_RUNTIME_DIR.")
    emitter.assert_debug(f"Using {str(state_dir)!r} for the state directory.")


@pytest.mark.usefixtures("state_dir")
def test_create_state_dir_file_exists_error(state_service_factory, state_dir):
    """Raise an error if the state directory already exists as a file."""
    state_dir.touch()
    expected_error = re.escape(
        f"Failed to create state dir at {str(state_dir)!r} because a "
        "file with that name already exists."
    )

    with pytest.raises(errors.StateServiceError, match=expected_error):
        state_service_factory()


def test_destroy_state_dir(state_service_factory, state_dir, monkeypatch):
    """Destroy the state directory when CRAFT_DEBUG isn't set."""
    monkeypatch.delenv(_const.CRAFT_DEBUG_ENV, raising=False)

    state_service = state_service_factory()
    assert state_dir.exists()
    state_service._destroy_state_dir()

    assert not state_dir.exists()


def test_keep_state_dir(state_service_factory, state_dir, monkeypatch):
    """Keep the state directory if CRAFT_DEBUG is set."""
    monkeypatch.setenv(_const.CRAFT_DEBUG_ENV, "y")

    state_service = state_service_factory()
    assert state_dir.exists()
    state_service._destroy_state_dir()

    assert state_dir.exists()


def test_configure_instance():
    """Configure the instance."""
    # No point in testing this since we need to switch to pushing and pulling state files in and out of instances


###########################
# Getter and setter tests #
###########################


def test_get_and_set(state_service_factory, state_dir, emitter):
    """Test getting and setting a value in the state service."""
    state_service = state_service_factory()

    state_service.set("foo", "bar", value="baz")
    value = state_service.get("foo", "bar")

    assert value == "baz"
    emitter.assert_debug("Setting 'foo.bar' to 'baz'.")
    emitter.assert_debug("Set 'foo.bar' to 'baz'.")
    emitter.assert_debug("Getting value for 'foo.bar'.")
    emitter.assert_debug("Got value 'baz' for 'foo.bar'.")


def test_get_invalid_path(state_service_factory, state_dir):
    """Error if an item the path doesn't exist."""
    state_service = state_service_factory()
    state_service.set("foo", "bar", value="baz")
    expected_error = re.escape(
        "Failed to get value for 'foo.non-existent': 'non-existent' doesn't exist."
    )

    with pytest.raises(KeyError, match=expected_error):
        state_service.get("foo", "non-existent")


def test_get_invalid_path_top_level(state_service_factory, state_dir):
    """Error if the top level item in the path doesn't exist."""
    state_service = state_service_factory()
    expected_error = re.escape(
        "Failed to get value for 'foo.bar.baz': 'foo' doesn't exist."
    )

    with pytest.raises(KeyError, match=expected_error):
        state_service.get("foo", "bar", "baz")


def test_get_non_dict_path(state_service_factory, state_dir):
    """Error if an item in the path isn't a dictionary."""
    state_service = state_service_factory()
    state_service.set("foo", "bar", value="baz")
    expected_error = re.escape(
        "Failed to get value for 'foo.bar.baz': can't traverse into node at 'bar'."
    )

    with pytest.raises(KeyError, match=expected_error):
        state_service.get("foo", "bar", "baz")


def test_get_no_keys(state_service_factory, state_dir):
    """Error if no keys are provided."""
    state_service = state_service_factory()
    expected_error = "No keys provided."

    with pytest.raises(KeyError, match=expected_error):
        state_service.get()


@pytest.mark.parametrize(
    "first_key",
    [
        "123$$$",
    ],
)
def test_invalid_first_key(first_key, state_service_factory, state_dir):
    """Error if the first key is invalid."""
    state_service = state_service_factory()
    expected_error = re.escape(
        f"The first key in '{first_key}.foo.bar' must only "
        "contain ASCII alphanumeric characters and _ (underscores)."
    )

    with pytest.raises(KeyError, match=expected_error):
        state_service.get(first_key, "foo", "bar")
