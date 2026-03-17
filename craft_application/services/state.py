# Copyright 2025 Canonical Ltd.
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
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""A service for handling global application state."""

from __future__ import annotations

import atexit
import os
import pathlib
import re
import shutil
import stat
import sys
from collections.abc import Sequence
from typing import TYPE_CHECKING, cast, final

import craft_cli
import craft_providers
import craft_providers.lxd
import platformdirs
import yaml

from craft_application import errors, util
from craft_application._const import CRAFT_DEBUG_ENV, CRAFT_STATE_DIR_ENV

from . import base

if TYPE_CHECKING:
    from craft_application.application import AppMetadata
    from craft_application.services import service_factory

ValueType = (
    str | int | float | bool | Sequence["ValueType"] | dict[str, "ValueType"] | None
)


class StateService(base.AppService):
    """A service for handling global application state.

    Commands and services can use the state service to store and retrieve information globally.
    It provides a way to pass information in between the outer (manager) and inner (managed)
    instances of an application.

    Data is accessed via structured paths. For example:

        state_service = app._services.get("state")
        state_service.set("artifacts", "platform-1", value="my-artifact.txt")
        state_service.get("artifacts", "platform-1")

    :raises StateServiceError: If the state directory can't be determined.
    :raises StateServiceError: If the state directory can't be created.
    """

    __state_dir: pathlib.Path
    """The path to the state directory."""

    @final
    def __init__(
        self, app: AppMetadata, services: service_factory.ServiceFactory
    ) -> None:
        super().__init__(app, services)
        self.__state_dir = self._get_state_dir()

        # only the outer instance manages the state dir
        if util.is_managed_mode():
            craft_cli.emit.debug("Not managing state directory in managed mode.")
        else:
            self._create_state_dir()
            atexit.register(self._destroy_state_dir)

    @final
    def get(self, *keys: str) -> ValueType:
        """Get the value at the given path.

        :param keys: A structured path to the value.

        :returns: The value for the key.

        :raises KeyError: If an item in the path doesn't exist.
        :raises KeyError: If an item in the path isn't a dictionary.
        :raises KeyError: If no keys are provided.
        :raises KeyError: If the first key isn't a string containing ASCII alphanumeric
            characters and _ (underscores).
        :raises StateServiceError: If a state file can't be loaded.
        """
        craft_cli.emit.debug(f"Getting value for {StateService._format_keys(*keys)!r}.")
        self._validate_keys(*keys)

        data = self._load_state_file(keys[0])

        try:
            value = self._get(*keys, data=data)
        except KeyError as err:
            raise KeyError(
                f"Failed to get value for {StateService._format_keys(*keys)!r}: {err.args[0]}"
            ) from err

        craft_cli.emit.debug(
            f"Got value {value!r} for {StateService._format_keys(*keys)!r}."
        )
        return value

    @final
    def set(self, *keys: str, value: ValueType, overwrite: bool = False) -> None:
        """Set the value at the given path.

        :param keys: A structured path to the value.
        :param value: The value to set.
        :param overwrite: Allow overwriting existing values.

        :raises KeyError: If an item in the path isn't a dictionary.
        :raises KeyError: If no keys are provided.
        :raises KeyError: If the first key isn't a string containing ASCII alphanumeric
            characters and _ (underscores).
        :raises TypeError: If the value is a dictionary.
        :raises ValueError: If the final item in the path already exists and 'overwrite' is false.
        :raises ValueError: If the state file would be greater than 1 MiB.
        """
        craft_cli.emit.debug(
            f"Setting {StateService._format_keys(*keys)!r} to {value!r}."
        )
        self._validate_keys(*keys)

        file_name = keys[0]
        data = self._load_state_file(file_name)

        try:
            self._set(*keys, data=data, value=value, overwrite=overwrite)
        except (KeyError, ValueError) as err:
            raise type(err)(
                f"Failed to set {StateService._format_keys(*keys)!r} to {value!r}: {err.args[0]}"
            ) from err

        self._save_state_file(file_name, data)

        craft_cli.emit.debug(f"Set {StateService._format_keys(*keys)!r} to {value!r}.")

    @final
    def configure_instance(self, instance: craft_providers.Executor) -> None:
        """Configure an instance for the state service.

        :param instance: The instance to configure.
        """
        craft_cli.emit.debug(
            f"Mounting state directory {str(self._state_dir)!r} to {str(self._managed_state_dir)!r}."
        )

        # give LXD access to the state directory when running as root
        if os.geteuid() == 0 and isinstance(instance, craft_providers.lxd.LXDInstance):
            craft_cli.emit.debug(
                f"Adding go+rwx permissions to {str(self._state_dir)!r}."
            )
            mode = self._state_dir.stat().st_mode
            new_mode = (
                mode
                | stat.S_IRGRP
                | stat.S_IWGRP
                | stat.S_IXGRP
                | stat.S_IROTH
                | stat.S_IWOTH
                | stat.S_IXOTH
            )
            self._state_dir.chmod(new_mode)

        instance.mount(host_source=self._state_dir, target=self._managed_state_dir)

    @final
    @property
    def _state_dir(self) -> pathlib.Path:
        """The path to the state directory."""
        return self.__state_dir

    @final
    @property
    def _managed_state_dir(self) -> pathlib.PurePosixPath:
        """The path to the managed state directory."""
        return pathlib.PurePosixPath("/tmp/craft-state")  # noqa: S108 (hardcoded-temp-file)

    @final
    def _get(self, *keys: str, data: dict[str, ValueType]) -> ValueType:
        """Recursive helper to get a value from a nested dictionary.

        :param keys: A structured path to the value. At least one key must be provided.
        :param data: The data structure to recurse into.

        :returns: The value for the key.

        :raises KeyError: If an item in the path doesn't exist.
        :raises KeyError: If an item in the path isn't a dictionary.
        """
        key, *remaining = keys

        try:
            data_at_key = data[key]
        except KeyError as err:
            raise KeyError(f"{key!r} doesn't exist.") from err

        if len(keys) == 1:
            return data_at_key

        if not isinstance(data_at_key, dict):
            raise KeyError(f"can't traverse into node at {key!r}.")

        return self._get(*remaining, data=data_at_key)

    @final
    def _set(
        self, *keys: str, data: dict[str, ValueType], value: ValueType, overwrite: bool
    ) -> None:
        """Recursive helper to set a value in a nested dictionary.

        :param keys: A structured path to the value. At least one key must be provided.
        :param data: The data structure to recurse into.
        :param value: The value to set.
        :param overwrite: Allow overwriting existing values.

        :raises KeyError: If an item in the path isn't a dictionary.
        :raises ValueError: If the final item in the path already exists and 'overwrite' is false.
        """
        key, *remaining = keys

        if len(keys) == 1:
            if key in data:
                if overwrite:
                    craft_cli.emit.debug("Overwriting existing value.")
                else:
                    raise ValueError(
                        f"key {key!r} already exists and overwrite is false."
                    )
            data[key] = value
            return

        data_at_key = data.setdefault(key, {})
        if not isinstance(data_at_key, dict):
            raise KeyError(f"can't traverse into node at {key!r}.")

        self._set(*remaining, data=data_at_key, value=value, overwrite=overwrite)

    @final
    def _destroy_state_dir(self) -> None:
        """Remove the state directory.

        If CRAFT_DEBUG is set, then the directory is never destroyed, even if the
        application exits with an error.
        """
        if not os.getenv(CRAFT_DEBUG_ENV):
            shutil.rmtree(self._state_dir)

    @final
    def _create_state_dir(self) -> None:
        """Create the state directory.

        :raises StateServiceError: If the directory can't be created.
        """
        try:
            self._state_dir.mkdir(parents=True, exist_ok=True)
        except FileExistsError as err:
            raise errors.StateServiceError(
                f"Failed to create state dir at {str(self._state_dir)!r} because a "
                "file with that name already exists."
            ) from err

    @final
    def _get_state_dir(self) -> pathlib.Path:
        """Get the state directory.

        Prefers, in order:
        1. /tmp/craft-state/, in managed mode.
        1. The CRAFT_STATE_DIR environment variable.
        2. XDG_RUNTIME_DIR environment variable and a subdirectory with the outer instance's PID.
        3. A temporary directory in the user's home directory.

        :raises StateServiceError: If the directory can't be determined.

        :returns: The path to the state directory.
        """
        if util.is_managed_mode():
            craft_cli.emit.debug("Getting state directory for a managed instance.")
            state_dir = pathlib.Path(self._managed_state_dir)
        elif state_dir_env := os.getenv(CRAFT_STATE_DIR_ENV):
            craft_cli.emit.debug(f"Getting state directory from {CRAFT_STATE_DIR_ENV}.")
            state_dir = pathlib.Path(state_dir_env)
        else:
            craft_cli.emit.debug("Getting runtime directory.")
            # Using the PID as a subdir prevents conflicts when running
            # multiple executions of the same application in parallel.
            state_dir = platformdirs.user_runtime_path(
                str(os.getpid()), ensure_exists=True
            )
            if sys.platform == "linux" and state_dir.is_relative_to("/tmp"):  # noqa: S108 (use of /tmp)
                # Use the home dir because the state dir will get mounted
                # in the instance and Multipass can't access /tmp.
                craft_cli.emit.debug("Getting home temporary directory.")
                state_dir = util.get_home_temporary_directory()

        state_dir = state_dir.resolve()
        craft_cli.emit.debug(f"Using {str(state_dir)!r} for the state directory.")
        return state_dir

    @final
    @staticmethod
    def _format_keys(*keys: str) -> str:
        return ".".join(keys)

    @final
    @staticmethod
    def _validate_keys(*keys: str) -> None:
        """Validate keys.

        :param *keys: A structured path to the value.

        :raises KeyError: If no keys are provided.
        :raises KeyError: If the first key isn't a string containing ASCII alphanumeric
            characters and _ (underscores).
        """
        if not keys:
            raise KeyError("No keys provided.")

        if not re.fullmatch(r"[A-Za-z0-9_]+", keys[0]):
            raise KeyError(
                f"The first key in {StateService._format_keys(*keys)!r} must only "
                "contain ASCII alphanumeric characters and _ (underscores)."
            )

    @final
    def _load_state_file(self, file_name: str) -> dict[str, ValueType]:
        """Load a state file.

        :param file_name: The name of the state file to load in the state directory
            with no file extension.

        :returns: A dictionary of state data or an empty dictionary if the file doesn't exist.

        :raises StateServiceError: If the state file can't be loaded.
        """
        file_path = self._state_dir / f"{file_name}.yaml"
        craft_cli.emit.debug(f"Loading state file {str(file_path)!r}.")

        try:
            if not file_path.exists():
                craft_cli.emit.debug("State file doesn't exist.")
                return {}
        except PermissionError as err:
            raise errors.StateServiceError(
                f"Can't load state file {str(file_path)!r} due to insufficient permissions."
            ) from err

        if not file_path.is_file():
            raise errors.StateServiceError(
                f"Can't load state file {str(file_path)!r} because it's not a regular file."
            )

        try:
            return cast(dict[str, ValueType], yaml.safe_load(file_path.read_text()))
        except OSError as err:
            raise errors.StateServiceError(
                message=f"Can't load state file {str(file_path)!r}.",
            ) from err
        except yaml.YAMLError as err:
            raise errors.StateServiceError(
                message=f"Can't parse state file {str(file_path)!r}.",
            ) from err

    @final
    def _save_state_file(self, file_name: str, data: dict[str, ValueType]) -> None:
        """Save a state file as YAML.

        Existing state files are overwritten.

        :param file_name: The name of the state file to save with no file extension.
        :param data: The data to save to the state file.

        :raises ValueError: If the state file would be greater than 1MiB in size.
        :raises StateServiceError: If the file can't be saved.
        """
        file_path = self._state_dir / f"{file_name}.yaml"
        craft_cli.emit.debug(f"Writing state to {str(file_path)!r}.")
        raw_data = util.dump_yaml(data)

        # There isn't a hard limit on the size of a state file but we shouldn't be serializing
        # an unlimited amount of data, so 1 MiB is a reasonable maximum.
        if len(raw_data) > 1024 * 1024:
            raise ValueError("Can't save state file over 1 MiB in size.")

        try:
            file_path.write_text(raw_data)
        # specific handling for permission errors as they are the most likely error to occur
        except PermissionError as err:
            raise errors.StateServiceError(
                f"Can't save state file {str(file_path)!r} due to insufficient permissions."
            ) from err
        except OSError as err:
            raise errors.StateServiceError(
                f"Can't save state file {str(file_path)!r}."
            ) from err
