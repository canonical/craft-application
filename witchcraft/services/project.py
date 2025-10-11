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
"""Witchcraft project service."""

from typing import Any

from craft_application.services import project
from craft_parts import ProjectVar, ProjectVarInfo
from typing_extensions import override


class ProjectService(project.ProjectService):
    """A service for handling access to the project."""

    @override
    def _create_project_vars(self, project: dict[str, Any]) -> ProjectVarInfo:
        """Create the project variables.

        Adds a top-level version.
        Adds a version for components, if defined in the project.
        """
        project_vars = {
            "version": ProjectVar(
                value=project.get("version"),
                part_name=project.get("adopt-info"),
            ).marshal(),
        }

        if components := project.get("components"):
            project_vars["components"] = {}
            for name, component in components.items():
                project_vars["components"][name] = {}
                project_vars["components"][name]["version"] = ProjectVar(
                    value=component.get("version"),
                    part_name=component.get("adopt-info"),
                ).marshal()

        return ProjectVarInfo.unmarshal(project_vars)
