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
"""General-purpose models for *craft applications."""

from craft_application.models.base import CraftBaseConfig, CraftBaseModel
from craft_application.models.constraints import (
    ProjectName,
    ProjectTitle,
    SummaryStr,
    UniqueStrList,
    VersionStr,
)
from craft_application.models.grammar import GrammarAwareProject
from craft_application.models.metadata import BaseMetadata
from craft_application.models.project import BuildInfo, BuildPlanner, Project


__all__ = [
    "BaseMetadata",
    "BuildInfo",
    "CraftBaseConfig",
    "CraftBaseModel",
    "GrammarAwareProject",
    "Project",
    "BuildPlanner",
    "ProjectName",
    "ProjectTitle",
    "SummaryStr",
    "UniqueStrList",
    "VersionStr",
]
