# This file is part of craft_application.
#
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
"""Witchcraft lifecycle service."""

import craft_platforms
from craft_application.services import lifecycle
from craft_parts.plugins import Plugin
from craft_parts.plugins.plugins import PluginGroup
from craft_parts.plugins.python_plugin import PythonPlugin
from craft_parts.plugins.rust_plugin import RustPlugin
from typing_extensions import override

MERLIN = PluginGroup.MINIMAL.value | {
    "python": PythonPlugin,
}
MORGANA = PluginGroup.MINIMAL.value | {"rust": RustPlugin}


class Lifecycle(lifecycle.LifecycleService):
    """Lifecycle service for witchcraft."""

    @override
    @staticmethod
    def get_plugin_group(
        build_info: craft_platforms.BuildInfo,
    ) -> dict[str, type[Plugin]] | None:
        if build_info.build_base.distribution != "ubuntu":
            return MORGANA
        if build_info.build_base <= craft_platforms.DistroBase("ubuntu", "22.04"):
            return MERLIN
        return MORGANA
