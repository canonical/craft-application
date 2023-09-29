# This file is part of craft-application.
#
# Copyright 2023 Canonical Ltd.
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
"""Basic project model for a craft-application.

This defines the structure of the input file (e.g. snapcraft.yaml)
"""
import dataclasses
from typing import Any, Dict, List, Optional, Union

import craft_parts
import craft_providers.bases
import pydantic
from pydantic import AnyUrl

from craft_application.models.base import CraftBaseModel
from craft_application.models.constraints import (
    ProjectName,
    ProjectTitle,
    SummaryStr,
    UniqueStrList,
    VersionStr,
)


@dataclasses.dataclass
class BuildInfo:
    """Platform build information."""

    platform: str
    """The platform name."""

    build_on: str
    """The architecture to build on."""

    build_for: str
    """The architecture to build for."""

    base: craft_providers.bases.BaseName
    """The base to build on."""


class Project(CraftBaseModel):
    """Craft Application project definition."""

    name: ProjectName
    title: Optional[ProjectTitle]
    version: VersionStr
    summary: Optional[SummaryStr]
    description: Optional[str]

    base: Optional[Any]

    contact: Optional[Union[str, UniqueStrList]]
    issues: Optional[Union[str, UniqueStrList]]
    source_code: Optional[AnyUrl]
    license: Optional[str]

    parts: Dict[str, Dict[str, Any]]  # parts are handled by craft-parts

    @pydantic.validator("parts", each_item=True)
    @classmethod
    def _validate_parts(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        """Verify each part (craft-parts will re-validate this)."""
        craft_parts.validate_part(item)
        return item

    @property
    def effective_base(self) -> Any:  # noqa: ANN401 app specific classes can improve
        """Return the base used for creating the output."""
        build_base = getattr(self, "build_base", None)
        if build_base is not None:
            return build_base
        if self.base is not None:
            return self.base
        raise RuntimeError("Could not determine effective base")

    def get_build_plan(self) -> List[BuildInfo]:
        """Obtain the list of architectures and bases from the project file."""
        raise NotImplementedError(
            f"{self.__class__.__name__!s} must implement get_build_plan"
        )
