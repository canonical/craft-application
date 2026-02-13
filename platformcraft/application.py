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
"""Application implementation for partitioncraft."""

import craft_application

from platformcraft.models.project import FancyProject

PLATFORMCRAFT = craft_application.AppMetadata(
    name="platformcraft",
    summary="A craft for testing custom platform definitions in craft-application.",
    docs_url="https://canonical-craft-application.readthedocs-hosted.com",
    source_ignore_patterns=["*.platformcraft"],
    project_variables=["version"],
    mandatory_adoptable_fields=["version"],
    ProjectClass=FancyProject,
)
