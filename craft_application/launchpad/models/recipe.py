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
"""Recipe classes."""

from __future__ import annotations

import enum
import time
from collections.abc import Collection, Iterable
from typing import TYPE_CHECKING

import lazr.restfulclient.errors  # type: ignore[import-untyped]
from typing_extensions import Any, Self, TypedDict, override

from .. import errors, util
from . import build
from .base import LaunchpadObject, Pocket

if TYPE_CHECKING:
    from .. import Launchpad


class RecipeType(enum.Enum):
    """The type of recipe."""

    SNAP = "snap"
    CHARM = "charm_recipe"


class BuildChannels(TypedDict, total=False):
    """Typed dictionary for the snap channels for recipe builds."""

    # Snaps and charms
    core: str
    core18: str
    core20: str
    core22: str
    core24: str

    charmcraft: str  # Charms only

    # Snaps only
    snapcraft: str
    snapd: str


class _BaseRecipe(LaunchpadObject):
    name: str
    """The name of the recipe."""
    owner_name: str
    """The name of the owner."""

    _resource_types = RecipeType
    _attr_map = {"owner_name": "owner.name"}

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}.get(name={self.name!r}, owner={self.owner_name!r})"

    @staticmethod
    def _fill_repo_info(
        kwargs: dict[str, Any],
        *,
        git_ref: str | None = None,
        bzr_branch: str | None = None,
    ) -> None:
        """Conditionally fill source repository info into keyword arguments."""
        if (git_ref and bzr_branch) or (not git_ref and not bzr_branch):
            raise ValueError(
                "A snap recipe must refer to a git repository or a bazaar branch, "
                "but not both.",
            )
        if git_ref:
            kwargs["git_ref"] = git_ref
        if bzr_branch:
            kwargs["branch"] = bzr_branch

    def get_builds(self) -> Collection[build.Build]:
        """Get the existing builds for a Recipe."""
        return [build.Build(self._lp, b) for b in self._obj.builds]

    def build(
        self,
        archive: str = "/ubuntu/+archive/primary",
        pocket: Pocket = Pocket.UPDATES,
        channels: BuildChannels | None = None,
        deadline: int | None = None,
    ) -> Collection[build.Build]:
        """Create a new set of builds for this recipe."""
        request_build_kwargs = {
            "archive": archive,
            "pocket": pocket.value,
        }
        if channels:
            request_build_kwargs["channels"] = channels
        build_request = self._obj.requestBuilds(**request_build_kwargs)
        sleep_time = 0.5
        while build_request.status == "Pending":
            # Check to see if we've run out of time.
            if deadline is not None and time.monotonic_ns() >= deadline:
                raise TimeoutError
            time.sleep(sleep_time)
            sleep_time *= 1.1
            build_request.lp_refresh()

        if build_request.status != "Completed":
            raise errors.BuildError("Build request failed")

        return [build.Build(self._lp, obj) for obj in build_request.builds]


class _StoreRecipe(_BaseRecipe):
    """A recipe for an item that has a store entry."""

    store_name: str
    """The name of the package in the store."""

    @staticmethod
    def _fill_store_info(
        kwargs: dict[str, Any],
        *,
        store_name: str | None,
        store_channels: Collection[str],
    ) -> None:
        """Conditionally fill store info into store-related keyword arguments."""
        if store_name:
            kwargs["store_name"] = store_name
            kwargs["store_channels"] = store_channels


class SnapRecipe(_StoreRecipe):
    """A recipe for a snap.

    https://api.launchpad.net/devel.html#snap
    """

    @classmethod
    @override
    def new(
        cls,
        lp: Launchpad,
        name: str,
        owner: str,
        *,
        architectures: Collection[str] | None = None,
        description: str | None = None,
        project: str | None = None,
        # Repository. Must be either a git repository or a Bazaar branch but not both.
        git_ref: str | None = None,
        # Bazaar:
        bzr_branch: str | None = None,
        # Automatic build options.
        auto_build: bool = False,
        auto_build_archive: str | None = None,
        auto_build_pocket: Pocket | str = Pocket.UPDATES,
        # Store options.
        store_name: str | None = None,
        store_channels: Collection[str] = ("latest/edge",),
    ) -> Self:
        """Create a new snap recipe.

        See: https://api.launchpad.net/devel.html#snaps-new

        :raises: ValueError for invalid configurations
        """
        kwargs: dict[str, Any] = {}
        if architectures:
            kwargs["processors"] = [
                util.get_architecture_name(arch) for arch in architectures
            ]
        if description:
            kwargs["description"] = description
        if project:
            kwargs["project"] = f"/{project}"
        cls._fill_repo_info(kwargs, git_ref=git_ref, bzr_branch=bzr_branch)
        cls._fill_store_info(
            kwargs,
            store_name=store_name,
            store_channels=store_channels,
        )

        if auto_build:
            kwargs["auto_build_pocket"] = auto_build_pocket
            if auto_build_archive:
                kwargs["auto_build_archive"] = auto_build_archive
        elif auto_build_archive:
            raise ValueError(
                "An auto-build archive may only be provided if auto-build is enabled.",
            )

        snap_entry = lp.lp.snaps.new(
            name=name,
            owner=util.get_person_link(owner),
            store_upload=bool(store_name),
            auto_build=auto_build,
            **kwargs,
        )

        return cls(lp, lp_obj=snap_entry)

    @classmethod
    @override
    def get(cls, lp: Launchpad, name: str, owner: str) -> Self:
        """Get an existing Snap recipe."""
        try:
            return cls(
                lp,
                lp.lp.snaps.getByName(owner=util.get_person_link(owner), name=name),
            )
        except lazr.restfulclient.errors.NotFound:
            raise ValueError(
                f"Could not find snap recipe {name!r} with owner {owner!r}",
            ) from None

    @classmethod
    @override
    def find(
        cls,
        lp: Launchpad,
        owner: str | None = None,
        store_name: str | None = None,
    ) -> Iterable[Self]:
        """Find Snap recipes"""
        owner = util.get_person_link(owner) if owner else None
        if store_name:
            if owner:
                lp_recipes = lp.lp.snaps.findByStoreName(
                    store_name=store_name,
                    owner=owner,
                )
            else:
                lp_recipes = lp.lp.snaps.findByStoreName(store_name)
        elif owner:
            lp_recipes = lp.lp.snaps.findByOwner(owner=owner)
        else:
            raise ValueError("Invalid search terms")

        for recipe in lp_recipes:
            yield cls(lp, recipe)


class CharmRecipe(_StoreRecipe):
    """A recipe for a charm.

    https://api.launchpad.net/devel.html#charm_recipe
    """

    @classmethod
    @override
    def new(
        cls,
        lp: Launchpad,
        name: str,
        owner: str,
        project: str,
        *,
        build_path: str | None = None,
        # Automatic build options.
        auto_build: bool = False,
        auto_build_channels: BuildChannels | None = None,
        # Store options.
        store_name: str | None = None,
        store_channels: Collection[str] = ("latest/edge",),
        git_ref: str | None = None,
    ) -> Self:
        """Create a new charm recipe.

        See: https://api.launchpad.net/devel.html#charm_recipes-new
        """
        kwargs = {}
        if auto_build:
            kwargs["auto_build_channels"] = auto_build_channels
        cls._fill_store_info(
            kwargs,
            store_name=store_name,
            store_channels=store_channels,
        )
        cls._fill_repo_info(kwargs, git_ref=git_ref)

        charm_entry = lp.lp.charm_recipes.new(
            name=name,
            owner=util.get_person_link(owner),
            project=f"/{project}",
            auto_build=auto_build,
            **kwargs,
        )

        return cls(lp, charm_entry)

    @classmethod
    @override
    def get(cls, lp: Launchpad, name: str, owner: str, project: str) -> Self:
        """Get a charm recipe."""
        try:
            return cls(
                lp,
                lp.lp.charm_recipes.getByName(
                    name=name,
                    owner=util.get_person_link(owner),
                    project=project,
                ),
            )
        except lazr.restfulclient.errors.NotFound:
            raise ValueError(
                f"Could not find charm recipe {name!r} in project {project!r} with owner {owner!r}",
            ) from None

    @classmethod
    @override
    def find(cls, lp: Launchpad, owner: str, *, name: str = "") -> Iterable[Self]:
        """Find a Charm recipe by the owner."""
        owner = util.get_person_link(owner)
        lp_recipes = lp.lp.charm_recipes.findByOwner(owner=util.get_person_link(owner))
        for recipe in lp_recipes:
            if name and recipe.name != name:
                continue
            yield cls(lp, recipe)


Recipe = SnapRecipe | CharmRecipe
