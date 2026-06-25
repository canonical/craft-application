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
"""Partitioncraft project service.

Needed so we can set partitions.
"""

import craft_platforms
import pydantic
from craft_application.services import project
from typing_extensions import override

from platformcraft.models.platform import FancyPlatformsDict


class ProjectService(project.ProjectService):
    """Package service for testcraft."""

    @override
    @classmethod
    def _preprocess_platforms(
        cls, platforms: dict[str, craft_platforms.PlatformDict]
    ) -> dict[str, craft_platforms.PlatformDict]:
        """Validate that the given platforms value is valid."""
        if platforms:
            cls._vectorise_platforms(platforms)
        platforms_project_adapter = pydantic.TypeAdapter(
            FancyPlatformsDict,
        )
        return platforms_project_adapter.dump_python(  # type: ignore[no-any-return]
            platforms_project_adapter.validate_python(platforms),
            mode="json",
            by_alias=True,
            exclude_defaults=True,
        )
