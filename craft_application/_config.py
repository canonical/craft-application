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
    """The configuration model for the app.

    This model informs the config service what configuration items are available
    to the application.
    """

    verbosity_level: EmitterMode = EmitterMode.BRIEF
    """The verbosity level for the app."""
    debug: bool = False
    """Whether the application is in debug mode."""
    build_environment: str | None = None
    """The build environment to use for this app.

    Defaults to unset, can also be set as ``host`` to enable destructive mode.
    """
    secrets: str

    platform: str | None = None
    """The platform for which to build."""
    build_for: str | None = None
    """The target architecture for which to build."""
    build_on: str | None = None
    """The architecture on which to build.

    This is ignored in destructive made and is only used for launching a provider.
    The provider is instructed about the requested architecture. If that architecture
    cannot run with the current system configuration, it will raise an error.
    """

    parallel_build_count: int
    """The parallel build count to send to Craft Parts.

    Supersedes any value set in ``max_parallel_build_count``.
    """
    max_parallel_build_count: int
    """The maximum parallel build count to send to Craft Parts.

    If this value is set but ``parallel_build_count`` is not, the smaller of
    ``max_parallel_build_count`` or the number of processor cores available to the
    app process is used. If unset, the number of processor cores available is used.
    """
    lxd_remote: str = "local"
    """The LXD remote to use if using the LXD provider."""
    launchpad_instance: str = "production"
    """The Launchpad instance to use for remote builds."""

    idle_mins: pydantic.NonNegativeInt | None = None
    """How long the container used by lifecycle steps remains active after the app exits.

    If unset, this defaults to exiting synchronously before the app exits.
    """
