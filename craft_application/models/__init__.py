# This file is part of craft_application.
#
# Copyright 2023-2024 Canonical Ltd.
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

from craft_application.models.base import CraftBaseModel
from craft_application.models.constraints import (
    ProjectName,
    ProjectTitle,
    SummaryStr,
    UniqueStrList,
    VersionStr,
    get_validator_by_regex,
)
from craft_application.models.grammar import (
    GrammarAwareProject,
    get_grammar_aware_part_keywords,
)
from craft_application.models.metadata import BaseMetadata
from craft_application.models.project import (
    DEVEL_BASE_INFOS,
    DEVEL_BASE_WARNING,
    BuildInfo,
    BuildPlanner,
    Platform,
    Project,
)


__all__ = [
    "BaseMetadata",
    "BuildInfo",
    "DEVEL_BASE_INFOS",
    "DEVEL_BASE_WARNING",
    "CraftBaseModel",
    "get_grammar_aware_part_keywords",
    "GrammarAwareProject",
    "Platform",
    "Project",
    "BuildPlanner",
    "ProjectName",
    "ProjectTitle",
    "SummaryStr",
    "UniqueStrList",
    "VersionStr",
    "get_validator_by_regex",
]
