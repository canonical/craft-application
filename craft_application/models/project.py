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
from typing import Any, Dict, Optional, Union, cast

import craft_parts
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


class Project(CraftBaseModel):
    """Craft Application project definition."""

    name: ProjectName
    title: Optional[ProjectTitle]
    base: Optional[Any]
    version: VersionStr
    contact: Optional[Union[str, UniqueStrList]]
    issues: Optional[Union[str, UniqueStrList]]
    source_code: Optional[AnyUrl]
    summary: Optional[SummaryStr]
    description: Optional[str]
    license: Optional[str]
    parts: Dict[str, Dict[str, Any]]  # parts are handled by craft-parts

    @pydantic.validator("parts", each_item=True)
    @classmethod
    def _validate_parts(cls, item: Dict[str, Any]) -> Dict[str, Any]:
        """Verify each part (craft-parts will re-validate this)."""
        craft_parts.validate_part(item)
        return item

    @property
    def effective_base(self) -> str:
        """Return the base used for creating the output."""
        if hasattr(self, "build_base"):
            if self.build_base is not None:  # pyright: ignore[reportGeneralTypeIssues]
                return cast(
                    str, self.build_base  # pyright: ignore[reportGeneralTypeIssues]
                )
        if self.base is not None:
            return cast(str, self.base)
        raise RuntimeError("Could not determine effective base")
