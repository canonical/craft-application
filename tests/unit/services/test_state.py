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
import sys
from collections.abc import Callable
from unittest import mock

import craft_providers
import craft_providers.lxd
import pytest
from craft_application import _const, errors
from craft_application.services import StateService, state


@pytest.fixture
def state_service_factory(app_metadata, fake_services) -> Callable[[], StateService]:
    """A factory for creating a state service.

    Useful when environment variables or mocks need to be configured
    before initializing the service.
    """

    def _get_service():
        """Return an instance of the StateService."""
        return state.StateService(app_metadata, fake_services)

    return _get_service


@pytest.fixture
def state_dir(monkeypatch, tmp_path) -> pathlib.Path:
    """Sets CRAFT_STATE_DIR to 'tmp_path/state'."""
    state_dir = (tmp_path / "state").resolve()
    monkeypatch.setenv(_const.CRAFT_STATE_DIR_ENV, str(state_dir))
    return state_dir


@pytest.fixture
def state_service(state_dir, state_service_factory) -> StateService:
    """Return an instance of the StateService.

    Uses a state dir of 'tmp_path/state'.
    """
    return state_service_factory()


@pytest.fixture
def no_state_dir_env_var(monkeypatch) -> None:
    """Ensure CRAFT_STATE_DIR is not set."""
    monkeypatch.delenv(_const.CRAFT_STATE_DIR_ENV, raising=False)


###########################
# Getter and setter tests #
###########################


def test_get_and_set(state_service, state_dir, emitter):
    """Test getting and setting a value in the state service."""
    state_service.set("foo", "bar", value="baz")
    value = state_service.get("foo", "bar")

    assert value == "baz"
    emitter.assert_debug("Setting 'foo.bar' to 'baz'.")
    emitter.assert_debug("Set 'foo.bar' to 'baz'.")
    emitter.assert_debug("Getting value for 'foo.bar'.")
    emitter.assert_debug("Got value 'baz' for 'foo.bar'.")


def test_get_invalid_path(state_service, state_dir):
    """Error if an item the path doesn't exist."""
    state_service.set("foo", "bar", value="baz")
    expected_error = re.escape(
        "Failed to get value for 'foo.non-existent': 'non-existent' doesn't exist."
    )

    with pytest.raises(KeyError, match=expected_error):
        state_service.get("foo", "non-existent")


def test_get_invalid_path_top_level(state_service, state_dir):
    """Error if the top level item in the path doesn't exist."""
    expected_error = re.escape(
        "Failed to get value for 'foo.bar.baz': 'foo' doesn't exist."
    )

    with pytest.raises(KeyError, match=expected_error):
        state_service.get("foo", "bar", "baz")


def test_get_non_dict_path(state_service, state_dir):
    """Error if an item in the path isn't a dictionary."""
    state_service.set("foo", "bar", value="baz")
    expected_error = re.escape(
        "Failed to get value for 'foo.bar.baz': can't traverse into node at 'bar'."
    )

    with pytest.raises(KeyError, match=expected_error):
        state_service.get("foo", "bar", "baz")


def test_set_non_dict_path(state_service, state_dir):
    """Error if an item in the path isn't a dictionary."""
    state_service.set("foo", "bar", value="baz")
    expected_error = re.escape(
        "Failed to set 'foo.bar.baz' to 'new-value': can't traverse into node at 'bar'."
    )

    with pytest.raises(KeyError, match=expected_error):
        state_service.set("foo", "bar", "baz", value="new-value")


@pytest.mark.parametrize(
    ("func", "kwargs"),
    [
        ("get", {}),
        ("set", {"value": "baz"}),
    ],
)
def test_get_no_keys(func, kwargs, state_service, state_dir):
    """Error if no keys are provided."""
    expected_error = "No keys provided."

    with pytest.raises(KeyError, match=expected_error):
        getattr(state_service, func)(**kwargs)


@pytest.mark.parametrize(
    "first_key",
    ["", " ", "123$$$"],
)
@pytest.mark.parametrize(
    ("func", "kwargs"),
    [
        ("get", {}),
        ("set", {"value": "baz"}),
    ],
)
def test_get_invalid_first_key(
    func, kwargs, first_key, state_service_factory, state_dir
):
    """Error if the first key is invalid."""
    state_service = state_service_factory()
    expected_error = re.escape(
        f"The first key in '{first_key}.foo.bar' must only "
        "contain ASCII alphanumeric characters and _ (underscores)."
    )

    with pytest.raises(KeyError, match=expected_error):
        getattr(state_service, func)(first_key, "foo", "bar", **kwargs)


def test_set_overwrite(state_service_factory, state_dir, emitter):
    """Overwrite an item that already exists."""
    state_service = state_service_factory()
    state_service.set("foo", "bar", value="baz")

    state_service.set("foo", "bar", value="new-value", overwrite=True)

    emitter.assert_debug("Setting 'foo.bar' to 'baz'.")
    emitter.assert_debug("Overwriting existing value.")
    emitter.assert_debug("Set 'foo.bar' to 'new-value'.")


def test_set_overwrite_error(state_service_factory, state_dir):
    """Error if overwrite is false."""
    state_service = state_service_factory()
    state_service.set("foo", "bar", value="baz")
    expected_error = re.escape(
        "Failed to set 'foo.bar' to 'new-value': key 'bar' already exists and overwrite is false."
    )

    with pytest.raises(ValueError, match=expected_error):
        state_service.set("foo", "bar", value="new-value", overwrite=False)


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
    emitter.assert_debug("Getting state directory for a managed instance.")
    emitter.assert_debug("Using '/tmp/craft-state' for the state directory.")
    emitter.assert_debug("Not managing state directory in managed mode.")


@pytest.mark.usefixtures("no_state_dir_env_var")
def test_state_dir_xdg(state_service_factory, monkeypatch, tmp_path, emitter):
    """Create the state dir from XDG_RUNTIME_DIR."""
    # on linux, '/tmp/pytest-...' will get replaced with a temporary dir in the home dir
    monkeypatch.setattr(sys, "platform", "other")
    state_dir = (tmp_path / "xdg_runtime" / str(os.getpid())).resolve()
    monkeypatch.setenv("XDG_RUNTIME_DIR", str(state_dir.parent))

    state_service_factory()

    # create the state directory in user mode
    assert state_dir.exists()
    emitter.assert_debug("Getting runtime directory.")
    emitter.assert_debug(f"Using {str(state_dir)!r} for the state directory.")


@pytest.mark.usefixtures("no_state_dir_env_var")
def test_state_dir_home_temp(
    state_service_factory, mocker, monkeypatch, tmp_path, emitter
):
    """Use a temp dir in the home dir instead of in '/tmp' on linux."""
    state_dir = (tmp_path / "state").resolve()
    mocker.patch(
        "craft_application.services.state.platformdirs.user_runtime_path",
        return_value=pathlib.Path("/tmp/statedir"),
    )
    mocker.patch(
        "craft_application.util.get_home_temporary_directory", return_value=state_dir
    )
    monkeypatch.setattr(sys, "platform", "linux")

    state_service_factory()

    # create the state directory in user mode
    emitter.assert_debug("Getting runtime directory.")
    emitter.assert_debug("Getting home temporary directory.")
    emitter.assert_debug(f"Using {str(state_dir)!r} for the state directory.")
    assert state_dir.exists()


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


def test_configure_instance(state_service, state_dir, emitter):
    """Configure the instance."""
    mock_instance = mock.Mock(spec=craft_providers.Executor)

    state_service.configure_instance(mock_instance)

    mock_instance.mount.assert_called_once_with(
        host_source=state_dir, target=pathlib.PurePosixPath("/tmp/craft-state")
    )
    emitter.assert_debug(
        f"Mounting state directory {str(state_dir)!r} to '/tmp/craft-state'."
    )


def test_configure_instance_lxd_root_user(state_service, state_dir, emitter, mocker):
    """Add o+rwx permissions when running as root with LXD."""
    mock_instance = mock.Mock(spec=craft_providers.lxd.LXDInstance)
    mocker.patch("os.geteuid", return_value=0)

    state_service.configure_instance(mock_instance)

    mock_instance.mount.assert_called_once_with(
        host_source=state_dir, target=pathlib.PurePosixPath("/tmp/craft-state")
    )
    assert (state_dir.stat().st_mode & 0o077) == 0o077
    emitter.assert_debug(f"Adding go+rwx permissions to {str(state_dir)!r}.")
    emitter.assert_debug(
        f"Mounting state directory {str(state_dir)!r} to '/tmp/craft-state'."
    )


###############################
# State file management tests #
###############################


def test_load_state_file(state_service, state_dir, emitter):
    """Load a state file."""
    (state_dir / "foo.yaml").write_text("foo: test-value")
    state_data = state_service._load_state_file("foo")

    assert state_data == {"foo": "test-value"}
    emitter.assert_debug(f"Loading state file {str(state_dir / 'foo.yaml')!r}.")


def test_load_state_file_nonexistent(state_service, state_dir, emitter):
    """Return an empty dict if the state file doesn't exist."""
    state_data = state_service._load_state_file("foo")

    assert state_data == {}
    emitter.assert_debug(f"Loading state file {str(state_dir / 'foo.yaml')!r}.")
    emitter.assert_debug("State file doesn't exist.")


def test_load_state_file_permission_error(state_service, state_dir, mocker):
    """Error if the state file can't be read."""
    mocker.patch(
        "craft_application.services.state.pathlib.Path.exists",
        side_effect=PermissionError,
    )
    expected_error = re.escape(
        f"Can't load state file {str(state_dir / 'foo.yaml')!r} due to insufficient permissions."
    )

    with pytest.raises(errors.StateServiceError, match=expected_error):
        state_service._load_state_file("foo")


def test_load_state_file_not_a_file(state_service, state_dir):
    """Error if a state file isn't a file."""
    (state_dir / "foo.yaml").mkdir()
    expected_error = re.escape(
        f"Can't load state file {str(state_dir / 'foo.yaml')!r} because it's not a regular file."
    )

    with pytest.raises(errors.StateServiceError, match=expected_error):
        state_service._load_state_file("foo")


def test_load_state_file_os_error(state_service, state_dir, mocker):
    """Error if reading the state file fails."""
    mocker.patch(
        "craft_application.services.state.pathlib.Path.read_text", side_effect=OSError
    )
    (state_dir / "foo.yaml").write_text("key: value")
    expected_error = re.escape(
        f"Can't load state file {str(state_dir / 'foo.yaml')!r}."
    )

    with pytest.raises(errors.StateServiceError, match=expected_error):
        state_service._load_state_file("foo")


def test_load_state_file_invalid_yaml(state_service, state_dir):
    """Error if the state file isn't valid YAML."""
    (state_dir / "foo.yaml").write_text("}invalid yaml")
    expected_error = re.escape(
        f"Can't parse state file {str(state_dir / 'foo.yaml')!r}."
    )

    with pytest.raises(errors.StateServiceError, match=expected_error):
        state_service._load_state_file("foo")


def test_save_state_file(state_service, state_dir, emitter):
    """Save a state file."""
    state_service._save_state_file("foo", {"foo": "test-value"})

    saved_file = state_dir / "foo.yaml"
    assert saved_file.exists()
    assert saved_file.read_text() == "foo: test-value\n"
    emitter.assert_debug(f"Writing state to {str(saved_file)!r}.")


@pytest.mark.slow
def test_save_state_file_large_file(state_service, state_dir, emitter):
    """Save files up to and including 1 MiB in size."""
    # exactly 1 MiB
    value = "a" * (1024 * 1024 - len("foo: \n"))

    state_service._save_state_file("foo", {"foo": value})

    saved_file = state_dir / "foo.yaml"
    assert saved_file.exists()
    assert saved_file.read_text() == f"foo: {value}\n"
    emitter.assert_debug(f"Writing state to {str(saved_file)!r}.")


@pytest.mark.slow
def test_save_state_file_large_file_error(state_service, state_dir):
    """Error if the file is greater than 1 MiB."""
    # exactly 1 MiB + 1 byte
    value = "a" * (1024 * 1024 - len("foo: \n") + 1)
    expected_error = re.escape("Can't save state file over 1 MiB in size.")

    with pytest.raises(ValueError, match=expected_error):
        state_service._save_state_file("foo", {"foo": value})


def test_save_state_file_permission_error(state_service, state_dir, mocker):
    """Error if the state file can't be saved due to insufficient permissions."""
    mocker.patch(
        "craft_application.services.state.pathlib.Path.write_text",
        side_effect=PermissionError,
    )
    expected_error = re.escape(
        f"Can't save state file {str(state_dir / 'foo.yaml')!r} due to insufficient permissions."
    )

    with pytest.raises(errors.StateServiceError, match=expected_error):
        state_service._save_state_file("foo", {"foo": "test-value"})


def test_save_state_file_os_error(state_service, state_dir, mocker):
    """Error if the state file can't be saved."""
    mocker.patch(
        "craft_application.services.state.pathlib.Path.write_text",
        side_effect=OSError,
    )
    expected_error = re.escape(
        f"Can't save state file {str(state_dir / 'foo.yaml')!r}."
    )

    with pytest.raises(errors.StateServiceError, match=expected_error):
        state_service._save_state_file("foo", {"foo": "test-value"})
