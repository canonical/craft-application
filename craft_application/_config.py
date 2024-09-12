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

import craft_cli
import pydantic


class ConfigModel(pydantic.BaseModel):
    """A configuration model for a craft application."""

    verbosity_level: craft_cli.EmitterMode = craft_cli.EmitterMode.BRIEF
    debug: bool = False
    build_environment: str | None = None
    secrets: str

    platform: str | None = None
    build_for: str | None = None

    parallel_build_count: int
    max_parallel_build_count: int
    lxd_remote: str = "local"
    launchpad_instance: str = "production"
