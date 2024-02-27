#  This file is part of craft-application.
#
#  Copyright 2024 Canonical Ltd.
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
"""Project class."""

# This file relies heavily on dynamic features from launchpadlib that cause pyright
# to complain a lot. As such, we're disabling several pyright checkers for this file
# since in this case they generate more noise than utility.
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportOptionalCall=false
# pyright: reportOptionalIterable=false
# pyright: reportOptionalSubscript=false
# pyright: reportIndexIssue=false

from __future__ import annotations  # noqa: I001

import enum
from collections.abc import Iterable

import launchpadlib.errors  # type: ignore[import-untyped]
from typing_extensions import Self, Any
from typing import TYPE_CHECKING

from ..models.base import LaunchpadObject
from .. import errors

if TYPE_CHECKING:
    from .. import Launchpad


class ProjectType(enum.Enum):
    """The possible types of project."""

    Project = "project"


class Project(LaunchpadObject):
    """A Launchpad Project.

    https://api.launchpad.net/devel.html#project
    """

    _resource_types = ProjectType
    _attr_map = {}

    name: str
    title: str
    display_name: str
    summary: str
    description: str

    @classmethod
    def new(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls,
        lp: Launchpad,
        title: str,
        name: str,
        display_name: str,
        summary: str,
        *,
        description: str | None = None,
        **kwargs: Any,  # noqa: ANN401
    ) -> Self:
        """Create a new project.

        https://api.launchpad.net/devel.html#projects-new_project
        """
        if description:
            kwargs["description"] = description
        return cls(
            lp,
            lp.lp.projects.new_project(
                title=title,
                name=name,
                display_name=display_name,
                summary=summary,
                **kwargs,
            ),
        )

    @classmethod
    def get(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls, lp: Launchpad, name: str
    ) -> Self:
        """Get an existing project."""
        try:
            return cls(lp, lp.lp.projects[name])
        except (launchpadlib.errors.NotFound, KeyError):
            raise errors.NotFoundError(f"Could not find project {name}")

    @classmethod
    def find(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls, lp: Launchpad, text: str
    ) -> Iterable[Self]:
        """Find projects by a search term."""
        for lp_project in lp.lp.projects.search(text):
            yield cls(lp, lp_project)
