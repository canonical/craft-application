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

"""Snap config file definitions and helpers."""

import os
import pathlib
from typing import Any, Literal

import pydantic
import yaml
from craft_cli import emit
from snaphelpers import SnapConfigOptions, SnapCtlError

from craft_application.errors import CraftValidationError


def is_running_from_snap(app_name: str) -> bool:
    """Check if the app is running from the snap.

    Matches against the snap name to avoid false positives. For example, if the
    application is not running as a snap but is inside a snapped terminal,
    `SNAP_NAME` will exist but be set to the terminal snap's name.

    :param app_name: The name of the application.

    :returns: True if the app is running from the snap.
    """
    return os.getenv("SNAP_NAME") == app_name and os.getenv("SNAP") is not None


def get_snap_base(app_name: str) -> str | None:
    """Get the base snap name from snap.yaml.

    :param app_name: The name of the application.

    :returns: The base snap name (e.g., 'core24') or None if not running from a snap
        or if the snap.yaml doesn't have a base defined.
    """
    if not is_running_from_snap(app_name):
        emit.debug(
            f"Not reading snap base because {app_name} is not running as a snap."
        )
        return None

    snap_dir = os.getenv("SNAP")
    if not snap_dir:
        emit.debug("SNAP environment variable not set.")
        return None

    snap_yaml_path = pathlib.Path(snap_dir) / "meta" / "snap.yaml"
    if not snap_yaml_path.exists():
        emit.debug(f"snap.yaml not found at {snap_yaml_path}")
        return None

    try:
        with open(snap_yaml_path, "r") as f:
            snap_data = yaml.safe_load(f)
        base = snap_data.get("base")
        if base:
            emit.debug(f"Found base snap: {base}")
        else:
            emit.debug("No base defined in snap.yaml")
        return base
    except (OSError, yaml.YAMLError) as error:
        emit.debug(f"Failed to read or parse snap.yaml: {error!r}")
        return None


class SnapConfig(pydantic.BaseModel, extra="forbid"):
    """Data stored in a snap config.

    :param provider: provider to use. Valid values are 'lxd' and 'multipass'.
    """

    provider: Literal["lxd", "multipass"] | None = None

    @pydantic.field_validator("provider", mode="before")
    @classmethod
    def normalize(cls, provider: str) -> str:
        """Normalize provider name."""
        return provider.lower().strip()

    @classmethod
    def unmarshal(cls, data: dict[str, Any]) -> "SnapConfig":
        """Create and populate a new ``SnapConfig`` object from dictionary data.

        The unmarshal method validates entries in the input dictionary, populating
        the corresponding fields in the data object.

        :param data: The dictionary data to unmarshal.

        :return: The newly created object.

        :raise TypeError: If data is not a dictionary.
        :raise ValueError: If data is invalid.
        """
        if not isinstance(data, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("snap config data is not a dictionary")

        try:
            snap_config = cls(**data)
        except pydantic.ValidationError as err:
            raise CraftValidationError.from_pydantic(
                err, file_name="snap config"
            ) from None

        return snap_config


def get_snap_config(app_name: str) -> SnapConfig | None:
    """Get validated snap configuration.

    :param app_name: The name of the application.

    :return: SnapConfig. If not running as a snap, return None.
    """
    if not is_running_from_snap(app_name):
        emit.debug(
            f"Not loading snap config because {app_name} is not running as a snap."
        )
        return None

    try:
        snap_config = SnapConfigOptions(keys=["provider"])
        # even if the initialization of SnapConfigOptions succeeds, `fetch()` may
        # raise the same errors since it makes calls to snapd
        snap_config.fetch()
    except (AttributeError, SnapCtlError) as error:
        # snaphelpers raises an error (either AttributeError or SnapCtlError) when
        # it fails to get the snap config. this can occur when running inside a
        # docker or podman container where snapd is not available
        emit.debug("Could not retrieve the snap config. Is snapd running?")
        emit.trace(f"snaphelpers error: {error!r}")
        return None

    emit.debug(f"Retrieved snap config: {snap_config.as_dict()}")

    return SnapConfig.unmarshal(snap_config.as_dict())
