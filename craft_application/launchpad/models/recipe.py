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

from __future__ import annotations

import enum
import time
from collections.abc import Collection, Iterable
from typing import TYPE_CHECKING

import lazr.restfulclient.errors  # type: ignore[import-untyped]
from typing_extensions import Any, Self, TypedDict, override

from ...util import retry
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
    """Typed dictionary for build dependency channels.

    The values in this dictionary describe the channel from which to retrieve each
    relevant snap for building. If not defined, the chosen channel will be the
    snap's default channel.
    """

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


class BaseRecipe(LaunchpadObject):
    """A base class for recipe types."""

    name: str
    """The name of the recipe."""
    owner_name: str
    """The name of the owner."""

    _resource_types = RecipeType
    _attr_map = {"owner_name": "owner.name"}

    def __repr__(self) -> str:
        # This violates the normal convention for a __repr__, but it does so because
        # the standard convention isn't particularly meaningful. We use `.get()` here
        # to indicate that using `.get` as the constructor is the preferred method.
        return f"{self.__class__.__name__}.get(name={self.name!r}, owner={self.owner_name!r})"

    @classmethod
    def get(
        cls, lp: Launchpad, name: str, owner: str, project: str | None = None
    ) -> Self:
        """Get an existing recipe."""
        raise NotImplementedError

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
        return [
            build.Build(self._lp, b)
            for b in self._obj.builds  # pyright: ignore[reportGeneralTypeIssues]
        ]

    def _build(self, deadline: int | None, kwargs: dict[str, Any]) -> list[build.Build]:
        """Get builds for this recipe.

        :param deadline: The time (on Python's `monotonic_ns` clock) after which we time out.
        :param kwargs: A dictionary of keyword arguments to pass to the requestBuilds
            method of this recipe. Keyword arguments vary by recipe type.

        See: https://api.launchpad.net/devel.html
        """
        build_request = self._obj.requestBuilds(**kwargs)
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


class _StoreRecipe(BaseRecipe):
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
    def new(  # noqa: PLR0913
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

        :param lp: The Launchpad client to use for this recipe.
        :param name: The recipe name
        :param owner: The username of the person or team who owns the recipe
        :param architectures: A collection of architecture names to build the recipe.
            If None, detects the architectures from `snapcraft.yaml`
        :param description: (Optional) A description of the recipe.
        :param project: (Optional) The name of the project to which to attach this recipe.
        :param git_ref: A link to a git repository and branch from which to build.
            Mutually exclusive with bzr_branch.
        :param bzr_branch: A link to a bazaar branch from which to build.
            Mutually exclusive with git_ref.
        :param auto_build: Whether to automatically build on pushes to the branch.
            (Defaults to False)
        :param auto_build_archive: (Optional) If auto_build is True, the Ubuntu archive
            to use as the base for automatic builds.
        :param auto_build_pocket: (Optional) If auto_build is True, the Ubuntu pocket
            to use as the base for automatic builds.
        :param store_name: (Optional) The name in the store to which to upload this snap.
        :param store_channels: (Optional) The channels onto which to publish the snap
            if uploaded.
        :returns: The Snap recipe.

        :raises: ValueError for invalid configurations
        """
        kwargs: dict[str, Any] = {}
        if architectures:
            kwargs["processors"] = [util.get_processor(arch) for arch in architectures]
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

        snap_entry = retry(
            f"create snap recipe {name!r}",
            lazr.restfulclient.errors.BadRequest,
            lp.lp.snaps.new,
            name=name,
            owner=util.get_person_link(owner),
            store_upload=bool(store_name),
            auto_build=auto_build,
            **kwargs,
        )

        if not snap_entry:
            raise ValueError("Failed to create snap recipe")

        return cls(lp, lp_obj=snap_entry)

    @classmethod
    @override
    def get(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls, lp: Launchpad, name: str, owner: str, project: Any = None
    ) -> Self:
        """Get an existing Snap recipe."""
        _ = project  # project is unused, bot
        try:
            return cls(
                lp,
                retry(
                    f"get snap recipe {name!r}",
                    lazr.restfulclient.errors.NotFound,
                    lp.lp.snaps.getByName,
                    owner=util.get_person_link(owner),
                    name=name,
                ),
            )
        except lazr.restfulclient.errors.NotFound:
            raise ValueError(
                f"Could not find snap recipe {name!r} with owner {owner!r}",
            ) from None

    @classmethod
    def find(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls,
        lp: Launchpad,
        owner: str | None = None,
        store_name: str | None = None,
    ) -> Iterable[Self]:
        """Find Snap recipes."""
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

    def build(
        self,
        archive: str = "/ubuntu/+archive/primary",
        pocket: Pocket = Pocket.UPDATES,
        channels: BuildChannels | None = None,
        deadline: int | None = None,
    ) -> Collection[build.Build]:
        """Create a new set of builds for this recipe."""
        request_build_kwargs: dict[str, Any] = {
            "archive": archive,
            "pocket": pocket.value,
        }
        if channels:
            request_build_kwargs["channels"] = channels
        return self._build(deadline, request_build_kwargs)


class CharmRecipe(_StoreRecipe):
    """A recipe for a charm.

    https://api.launchpad.net/devel.html#charm_recipe
    """

    @classmethod
    def new(  # noqa: PLR0913
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

        :param lp: The Launchpad client to use for this recipe.
        :param name: The recipe name
        :param owner: The username of the person or team who owns the recipe
        :param project: The name of the project to which this recipe should be attached.
        :param build_path: (Optional) The path to the directory containing
            charmcraft.yaml (if it's not the root directory).
        :param git_ref: A link to a git repository and branch from which to build.
            Mutually exclusive with bzr_branch.
        :param auto_build: Whether to automatically build on pushes to the branch.
            (Defaults to False)
        :param auto_build_channels: (Optional) A dictionary of channels to use for
            snaps installed in the build environment.
        :param store_name: (Optional) The name in the store to which to upload this
            charm.
        :param store_channels: (Optional) The channels onto which to publish the charm
            if uploaded.
        :returns: The Charm recipe.
        """
        kwargs: dict[str, Any] = {}
        if auto_build:
            kwargs["auto_build_channels"] = auto_build_channels
        if build_path:
            kwargs["build_path"] = build_path
        cls._fill_store_info(
            kwargs,
            store_name=store_name,
            store_channels=store_channels,
        )
        cls._fill_repo_info(kwargs, git_ref=git_ref)

        charm_entry = retry(
            f"create charm recipe {name!r}",
            lazr.restfulclient.errors.BadRequest,
            lp.lp.charm_recipes.new,
            name=name,
            owner=util.get_person_link(owner),
            project=f"/{project}",
            auto_build=auto_build,
            **kwargs,
        )

        if not charm_entry:
            raise ValueError("Failed to create charm recipe")

        return cls(lp, charm_entry)

    @classmethod
    def get(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls, lp: Launchpad, name: str, owner: str, project: str | None = None
    ) -> Self:
        """Get a charm recipe."""
        try:
            return cls(
                lp,
                retry(
                    f"get charm recipe {name!r}",
                    lazr.restfulclient.errors.NotFound,
                    lp.lp.charm_recipes.getByName,
                    name=name,
                    owner=util.get_person_link(owner),
                    project=f"/{project}",
                ),
            )
        except lazr.restfulclient.errors.NotFound:
            raise ValueError(
                f"Could not find charm recipe {name!r} in project {project!r} with owner {owner!r}",
            ) from None

    @classmethod
    def find(  # pyright: ignore[reportIncompatibleMethodOverride]
        cls, lp: Launchpad, owner: str, *, name: str = ""
    ) -> Iterable[Self]:
        """Find a Charm recipe by the owner."""
        owner = util.get_person_link(owner)
        lp_recipes = lp.lp.charm_recipes.findByOwner(owner=util.get_person_link(owner))
        for recipe in lp_recipes:
            if name and recipe.name != name:
                continue
            yield cls(lp, recipe)

    def build(
        self,
        channels: BuildChannels | None = None,
        deadline: int | None = None,
    ) -> Collection[build.Build]:
        """Create a new set of builds for this recipe."""
        kwargs = {"channels": channels} if channels else {}
        return self._build(deadline, kwargs)


Recipe = SnapRecipe | CharmRecipe
