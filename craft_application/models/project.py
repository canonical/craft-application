# This file is part of craft-application.
#
#  Copyright 2023 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Basic project model for a craft-application.

This defines the structure of the input file (e.g. snapcraft.yaml)
"""
import pathlib
from typing import (
    TYPE_CHECKING,
    Any,
    Dict,
    List,
    Optional,
    Union,
    cast,
)

import craft_parts
import pydantic
from pydantic import AnyUrl

if TYPE_CHECKING:
    pass

from craft_application import errors
from craft_application.models.base import CraftBaseModel
from craft_application.models.constraints import (
    ProjectName,
    ProjectTitle,
    SummaryStr,
    UniqueStrList,
    VersionStr,
)
from craft_application.util import safe_yaml_load


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

    @classmethod
    def unmarshal(cls, data: Dict[str, Any]) -> "Project":
        """Create and populate a new ``Project`` object from dictionary data.

        The unmarshal method validates entries in the input dictionary, populating
        the corresponding fields in the data object.
        :param data: The dictionary data to unmarshal.
        :return: The newly created object.
        :raise TypeError: If data is not a dictionary.
        """
        if not isinstance(data, dict):
            raise TypeError("Project data is not a dictionary")

        return cls(**data)

    @classmethod
    def from_file(cls, project_file: pathlib.Path) -> "Project":
        """Create and populate a new ``Project`` object from ``project_file``."""
        if not project_file.exists():
            raise errors.ProjectFileMissingError(
                f"Could not find project file {str(project_file)!r}"
            )
        with project_file.open() as project_stream:
            # Ruff is detecting this as a potentially-unsafe load, which can be
            # overridden.
            project_data = safe_yaml_load(project_stream)
        try:
            return cls.unmarshal(project_data)
        except pydantic.ValidationError as err:
            raise errors.CraftValidationError.from_pydantic(
                err, file_name=project_file.name
            )

    def marshal(self) -> Dict[str, Union[str, List[str], Dict[str, Any]]]:
        """Convert to a dictionary."""
        return self.dict(by_alias=True, exclude_unset=True)

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
