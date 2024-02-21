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
"""Source code repositories."""
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
from __future__ import annotations

import datetime
import enum
from abc import ABCMeta
from collections.abc import Collection
from typing import TYPE_CHECKING, cast

from typing_extensions import Self

from .. import errors
from .base import InformationType, LaunchpadObject

if TYPE_CHECKING:
    from ..launchpad import Launchpad


class _BaseRepository(LaunchpadObject, metaclass=ABCMeta):
    """A base object for various repository types."""

    def get_access_token(
        self,
        description: str,
        scopes: Collection[str] = ("repository:push",),
        expiry: datetime.datetime | None = None,
    ) -> str:
        """Get a personal access token for pushing to the repository over HTTPS."""
        return str(
            self._obj.issueAccessToken(
                description=description, scopes=scopes, date_expires=expiry
            )
        )


class GitResourceTypes(enum.Enum):
    """Resource types for a git repository."""

    GIT_REPOSITORY = "git_repository"


class GitRepository(_BaseRepository):
    """A Git repository.

    https://api.launchpad.net/devel.html#git_repository
    """

    _resource_types = GitResourceTypes
    _attr_map = {"owner_name": "owner.name"}

    date_created: datetime.date
    date_last_modified: datetime.date
    date_last_repacked: datetime.date
    date_last_scanned: datetime.date
    default_branch: str
    description: str
    display_name: str
    git_https_url: str
    git_ssh_url: str
    name: str
    owner_default: bool
    private: bool
    owner_name: str

    @property
    def information_type(self) -> InformationType:
        """The type of information contained in this repository."""
        return InformationType(self._obj.information_type)

    @information_type.setter
    def information_type(self, value: InformationType | str) -> None:
        if isinstance(value, str):
            try:
                value = InformationType[value.upper()]
            except KeyError:
                value = InformationType(value)
        self._obj.information_type = value.value

    @classmethod
    def get(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls,
        lp: Launchpad,
        name: str | None = None,
        owner: str | None = None,
        project: str | None = None,
        path: str | None = None,
    ) -> Self:
        """Get an existing repository."""
        if path:
            if name or owner or project:
                raise ValueError("Do not set other values when a path is known.")
        elif project and owner:
            path = f"~{owner}/{project}/{name}"
        elif project:
            path = f"{project}/{name}"
        elif name:
            if owner is None:
                owner = lp.lp.me.name
            path = f"~{owner}/+git/{name}"
        else:
            raise NotImplementedError("Unknown how to find repo.")
        lp_repo = lp.lp.git_repositories.getByPath(path=path)
        if lp_repo is None:
            raise errors.NotFoundError(f"Could not find repository at path {path}")
        return cls(lp, lp_repo)

    @classmethod
    def new(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls,
        lp: Launchpad,
        name: str,
        owner: str | None = None,
        target: str | None = None,
        information_type: InformationType = InformationType.PUBLIC,
    ) -> Self:
        """Create a new git repository."""
        if owner is None:
            owner = cast(str, lp.lp.me.name)
        if target is None:
            repo = lp.lp.git_repositories.new(
                name=name,
                owner=f"/~{owner}",
                information_type=information_type.value,
            )
        else:
            repo = lp.lp.git_repositories.new(
                name=name,
                owner=f"/~{owner}",
                target=f"/{target}",
                information_type=information_type.value,
            )

        return cls(lp, repo)
