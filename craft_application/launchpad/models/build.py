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
"""Launchpad builds."""
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
import enum

import lazr.restfulclient.errors  # type: ignore[import-untyped]
from typing_extensions import Self

from .. import errors, util
from . import distro
from .base import LaunchpadObject


class BuildTypes(enum.Enum):
    """Types of build in Launchpad.

    There are more, but these are the only ones we currently support.
    """

    SNAP_BUILD = "snap_build"
    CHARM_BUILD = "charm_recipe_build"


class BuildState(enum.Enum):
    """States of a build."""

    PENDING = "Needs building"
    DEPENDENCY_WAIT = "Dependency wait"
    SUCCESS = "Successfully built"
    FAILED = "Failed to build"
    UPLOADING = "Uploading build"
    UPLOAD_FAILED = "Failed to upload"
    CHROOT_PROBLEM = "Chroot problem"
    SUPERSEDED = "Build for superseded Source"
    BUILDING = "Currently building"
    CANCELLING = "Cancelling build"
    CANCELLED = "Cancelled build"
    GATHERING_OUTPUT = "Gathering build output"

    @property
    def is_queued(self) -> bool:
        """Determine whether this state means the build is queued."""
        return self in (BuildState.PENDING, BuildState.DEPENDENCY_WAIT)

    @property
    def is_running(self) -> bool:
        """Determine whether this state means the build is running."""
        return self in (BuildState.BUILDING, BuildState.GATHERING_OUTPUT)

    @property
    def is_stopped(self) -> bool:
        """Determine whether this state means the build is done."""
        return self in (
            BuildState.SUCCESS,
            BuildState.FAILED,
            BuildState.UPLOAD_FAILED,
            BuildState.CHROOT_PROBLEM,
            BuildState.SUPERSEDED,
            BuildState.CANCELLED,
        )

    @property
    def is_stopping_or_stopped(self) -> bool:
        """Return True if the build is stopping or stopped."""
        return self == BuildState.CANCELLING or self.is_stopped


class Build(LaunchpadObject):
    """A build on the Launchpad build farm.

    https://api.launchpad.net/devel.html#build
    """

    _resource_types = BuildTypes
    _attr_map = {"architecture": "arch_tag"}

    self_link: str
    web_link: str
    resource_type_link: str
    build_log_url: str
    architecture: util.Architecture
    distribution: distro.Distribution
    distro_series: distro.DistroSeries

    @classmethod
    def new(cls) -> Self:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Do not create a build without a recipe."""
        raise NotImplementedError("Use a recipe's `build` method instead.")

    @classmethod
    def get(cls) -> Self:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Do not try to get builds without a recipe."""
        raise NotImplementedError("Use a recipe's `get_builds` method instead.")

    def get_state(self) -> BuildState:
        """Get the current state of this build."""
        return BuildState(self._obj.buildstate)

    def cancel(self) -> None:
        """Cancel this build."""
        try:
            self._obj.cancel()
        except lazr.restfulclient.errors.BadRequest as exc:
            state = self.get_state()
            if state.is_stopped or state == BuildState.CANCELLING:
                return
            raise errors.BuildError(exc.content.decode()) from exc

    def retry(self) -> None:
        """Retry this build."""
        try:
            self._obj.retry()
        except lazr.restfulclient.errors.BadRequest as exc:
            raise errors.BuildError(exc.content.decode()) from exc

    def get_artifact_urls(self) -> list[str]:
        """Get the URLs of build artifacts."""
        return list(self._obj.getFileUrls())
