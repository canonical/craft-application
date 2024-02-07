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

import pathlib

import launchpadlib.launchpad  # type: ignore[import-untyped]
import launchpadlib.uris  # type: ignore[import-untyped]
import platformdirs
from typing_extensions import Any, Self

from . import models

DEFAULT_CACHE_PATH = platformdirs.user_cache_path("launchpad-client")


class Launchpad:
    """A client for Launchpad."""

    def __init__(
        self, app_name: str, launchpad: launchpadlib.launchpad.Launchpad
    ) -> None:
        self.app_name = app_name
        self.lp = launchpad

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
        **kwargs: Any,
    ) -> Self:
        """Login to Launchpad."""
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

    def get_recipe(
        self,
        type_: models.RecipeType | str,
        name: str,
        owner: str,
        project: str | None = None,
    ) -> models.Recipe:
        """Get a recipe.

        :param type_: The type of recipe to get.
        :param owner: The owner of the recipe.
        :param name: The name of the recipe.
        :param project: (Optional) The project to which the recipe is attached
        :returns: A Recipe object of the appropriate type.
        :raises: ValueError if the type requested is invalid.

        A charm recipe requires a project. If none is given, the first charm matching
        the owner and name is returned, even if multiple recipes exist.
        """
        if isinstance(type_, str):
            type_ = models.RecipeType.__members__.get(type_.upper(), type_)
            type_ = models.RecipeType(type_)

        if type_ is models.RecipeType.SNAP:
            return models.SnapRecipe.get(self, name, owner)
        if type_ is models.RecipeType.CHARM:
            if project:
                return models.CharmRecipe.get(self, name, owner, project)
            result = None
            for recipe in models.CharmRecipe.find(self, owner, name=name):
                if recipe is not None:
                    raise ValueError(
                        f"Multiple charm recipes for {name!r} found with owner {owner!r}",
                    )
                result = recipe
            if result is None:
                raise ValueError(
                    f"Could not find charm recipe {name!r} with owner {owner!r}",
                )
            return result

        raise TypeError(f"Unknown recipe type: {type_}")

    def get_project(self, name: str) -> models.Project:
        """Get a project."""
        return models.Project.get(self, name)
