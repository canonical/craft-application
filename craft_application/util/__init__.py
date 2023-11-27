# This file is part of craft_application.
#
# Copyright 2023 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Utilities for craft-application."""

from craft_application.util.callbacks import get_unique_callbacks
from craft_application.util.logging import setup_loggers
from craft_application.util.paths import get_managed_logpath
from craft_application.util.platforms import (
    get_host_architecture,
    convert_architecture_deb_to_platform,
)
from craft_application.util.yaml import dump_yaml, safe_yaml_load

__all__ = [
    "get_unique_callbacks",
    "setup_loggers",
    "get_managed_logpath",
    "get_host_architecture",
    "convert_architecture_deb_to_platform",
    "dump_yaml",
    "safe_yaml_load",
]
