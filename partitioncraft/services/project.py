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

from craft_application.services import project


class PartitioncraftProjectService(project.ProjectService):
    """Package service for testcraft."""

    def get_partitions(self) -> list[str] | None:
        """Get the partitions needed for any partitioncraft project."""
        return ["default", "mushroom"]
