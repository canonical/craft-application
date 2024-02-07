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
import enum
from typing import Any

import lazr.restfulclient.errors
from typing_extensions import Self

from .. import errors, util
from .base import LaunchpadObject


class BuildTypes(enum.Enum):
    SNAP_BUILD = "snap_build"


class BuildState(enum.Enum):
    """States of a build."""

    PENDING = "Needs building"
    DEPENDENCY_WAIT = "Dependency wait"
    SUCCESS = "Successfully built"
    FAILED = "Failed to build"
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
        return self in (self.PENDING, self.DEPENDENCY_WAIT)

    @property
    def is_running(self) -> bool:
        """Determine whether this state means the build is running."""
        return self in (self.BUILDING, self.GATHERING_OUTPUT)

    @property
    def is_stopped(self) -> bool:
        """Determine whether this state means the build is done."""
        return self in (
            self.SUCCESS,
            self.FAILED,
            self.UPLOAD_FAILED,
            self.CHROOT_PROBLEM,
            self.SUPERSEDED,
            self.CANCELLED,
        )

    @property
    def is_stopping_or_stopped(self) -> bool:
        """Return True if the build is stopping or stopped."""
        return self == self.CANCELLING or self.is_stopped


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

    @classmethod
    def new(cls, *args: Any, **kwargs: Any) -> Self:
        raise NotImplementedError

    @classmethod
    def get(cls, *args: Any, **kwargs: Any) -> Self:
        raise NotImplementedError

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
