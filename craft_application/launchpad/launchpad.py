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
"""Main Launchpad client."""

# This file relies heavily on dynamic features from launchpadlib that cause pyright
# to complain a lot. As such, we're disabling several pyright checkers for this file
# since in this case they generate more noise than utility.
# pyright: reportUnknownMemberType=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportOptionalMemberAccess=false
# pyright: reportUnknownArgumentType=false

from __future__ import annotations

import pathlib
from typing import Any, Literal, overload

import launchpadlib.launchpad  # type: ignore[import-untyped]
import launchpadlib.uris  # type: ignore[import-untyped]
import lazr.restfulclient.errors  # type: ignore[import-untyped]
import platformdirs
from typing_extensions import Self

from . import models

DEFAULT_CACHE_PATH = platformdirs.user_cache_path("launchpad-client")


class Launchpad:
    """A client for Launchpad."""

    def __init__(
        self, app_name: str, launchpad: launchpadlib.launchpad.Launchpad
    ) -> None:
        self.app_name = app_name
        self.lp = launchpad
        try:
            self.username = str(self.lp.me.name)
        except lazr.restfulclient.errors.Unauthorized:
            self.username = "anonymous"

    @classmethod
    def anonymous(
        cls,
        app_name: str,
        root: str = launchpadlib.uris.LPNET_SERVICE_ROOT,
        cache_dir: pathlib.Path | None = DEFAULT_CACHE_PATH,
        version: str = "devel",
        timeout: int | None = None,
    ) -> Self:
        """Get an anonymous Launchpad client."""
        if cache_dir:
            cache_dir = cache_dir.expanduser().resolve()
            cache_dir.expanduser().resolve().mkdir(exist_ok=True, parents=True)
        return cls(
            app_name,
            launchpadlib.launchpad.Launchpad.login_anonymously(
                consumer_name=app_name,
                service_root=root,
                launchpadlib_dir=cache_dir,
                version=version,
                timeout=timeout,
            ),
        )

    @classmethod
    def login(
        cls,
        app_name: str,
        root: str = launchpadlib.uris.LPNET_SERVICE_ROOT,
        cache_dir: pathlib.Path | None = DEFAULT_CACHE_PATH,
        credentials_file: pathlib.Path | None = None,
        version: str = "devel",
        **kwargs: Any,  # noqa: ANN401 (Intentionally duck-typed)
    ) -> Self:
        """Login to Launchpad."""
        if cache_dir:
            cache_dir.expanduser().resolve()
            cache_dir.mkdir(exist_ok=True, parents=True)
        if credentials_file:
            credentials_file.expanduser().resolve()
            credentials_file.parent.mkdir(mode=0o700, exist_ok=True, parents=True)
        return cls(
            app_name,
            launchpadlib.launchpad.Launchpad.login_with(
                application_name=app_name,
                service_root=root,
                launchpadlib_dir=cache_dir,
                credentials_file=credentials_file,
                version=version,
                **kwargs,
            ),
        )

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}({self.app_name!r})"

    @overload
    def get_recipe(
        self,
        type_: Literal["snap", "SNAP", models.RecipeType.SNAP],
        name: str,
        owner: str | None,
    ) -> models.SnapRecipe: ...

    @overload
    def get_recipe(
        self,
        type_: Literal["charm", "CHARM", models.RecipeType.CHARM],
        name: str,
        owner: str | None,
        project: str,
    ) -> models.CharmRecipe: ...

    def get_recipe(
        self,
        type_: models.RecipeType | str,
        name: str,
        owner: str | None = None,
        project: str | None = None,
    ) -> models.Recipe:
        """Get a recipe.

        :param type_: The type of recipe to get.
        :param name: The name of the recipe.
        :param owner: (Optional) The owner of the recipe, defaults to oneself.
        :param project: (Optional) The project to which the recipe is attached
        :returns: A Recipe object of the appropriate type.
        :raises: ValueError if the type requested is invalid.

        Different recipe types may have different requirements. For example, a
        snap recipe only requires a name and an owner. However, a charm requires
        a project as well. If a charm recipe is requested and no project name is
        provided, the first recipe matching the owner and name is returned, even
        if multiple recipes exist.
        """
        if isinstance(type_, str):
            type_ = models.RecipeType.__members__.get(type_.upper(), type_)
            type_ = models.RecipeType(type_)
        if owner is None:
            owner = self.username

        if type_ is models.RecipeType.SNAP:
            return models.SnapRecipe.get(self, name, owner)
        if type_ is models.RecipeType.CHARM:
            if not project:
                raise ValueError("A charm recipe must be associated with a project.")
            return models.CharmRecipe.get(self, name, owner, project)

        raise TypeError(f"Unknown recipe type: {type_}")

    def get_project(self, name: str) -> models.Project:
        """Get a project."""
        return models.Project.get(self, name)

    def new_project(
        self,
        name: str,
        *,
        title: str,
        display_name: str,
        summary: str,
        description: str | None = None,
    ) -> models.Project:
        """Create a new project."""
        return models.Project.new(
            self, title, name, display_name, summary, description=description
        )

    @overload
    def get_repository(self, *, path: str) -> models.GitRepository: ...

    @overload
    def get_repository(
        self, *, name: str, owner: str | None = None, project: str | None = None
    ) -> models.GitRepository: ...

    def get_repository(
        self,
        *,
        name: str | None = None,
        owner: str | None = None,
        project: str | None = None,
        path: str | None = None,
    ) -> models.GitRepository:
        """Get an existing git repository.

        :param name: The name of the repository.
        :param owner: The owner of the repository. Optional, defaults to oneself.
        :param project: (Optional) The project to which the repository is attached.
        :param path: The full path of the repository. Mutually exclusive with other options.
        :returns: A GitRepository matching this repository.
        :raises: NotFoundError if the repository couldn't be found.
        """
        if path and (name or owner or project):
            raise ValueError(
                "Do not set repository name, owner or project when using a path."
            )
        if not path and not name:
            raise ValueError(
                "Must specify either the name or the path of the repository."
            )

        if not path:
            if not owner:
                owner = self.username
            if project:
                path = f"~{owner}/{project}/+git/{name}"
            else:
                path = f"~{owner}/+git/{name}"

        return models.GitRepository.get(self, path=path)

    def new_repository(
        self,
        name: str,
        owner: str | None = None,
        project: str | models.Project | None = None,
    ) -> models.GitRepository:
        """Create a new git repository.

        :param name: The name of the repository.
        :param owner: (Optional) the username of the owner (defaults to oneself).
        :param project: (Optional) the project to which the repository will be attached.
        """
        if isinstance(project, models.Project):
            project = project.name
        if owner is None:
            owner = self.username

        return models.GitRepository.new(self, name, owner, project)
