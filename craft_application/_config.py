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
"""Configuration model for craft applications."""

from __future__ import annotations

import pydantic
from craft_cli import EmitterMode


class ConfigModel(pydantic.BaseModel):
    """A configuration model for a craft application."""

    verbosity_level: EmitterMode = EmitterMode.BRIEF
    """The verbosity level for the app."""
    debug: bool = False
    """Whether the application is in debug mode."""
    build_environment: str | None = None
    """The build environment to use for this  application.

    Defaults to unset, can also be set as ``host``.
    """
    secrets: str

    platform: str | None = None
    """The platform for which to build."""
    build_for: str | None = None
    """The target architecture for which to build."""

    parallel_build_count: int
    """The parallel build count to send to craft-parts."""
    max_parallel_build_count: int
    """The maximum parallel build count to send to craft-parts."""
    lxd_remote: str = "local"
    """The LXD remote to use if using the LXD provider."""
    launchpad_instance: str = "production"
    """The Launchpad instance to use for remote builds."""

    idle_mins: pydantic.NonNegativeInt | None = None
    """How long to let the build container or VM idle before exiting.

    If unset, this defaults to exiting synchronously before the app exits.
    """
