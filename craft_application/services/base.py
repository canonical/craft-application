#  This file is part of craft-application.
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
"""Abstract base service class."""

from __future__ import annotations

import abc
import typing

from craft_cli import emit

from craft_application import errors

if typing.TYPE_CHECKING:
    from craft_platforms import BuildInfo

    from craft_application.application import AppMetadata
    from craft_application.models.project import Project
    from craft_application.services import ServiceFactory


# This is abstract to prevent it from being used directly. Ignore the lack of
# abstract methods.
class AppService(metaclass=abc.ABCMeta):  # noqa: B024
    """A service class, containing application business logic.

    The AppService base class is for services that do not need access to an
    existing project.
    """

    def __init__(self, app: AppMetadata, services: ServiceFactory) -> None:
        self._app = app
        self._services = services

    def setup(self) -> None:
        """Service-specific setup to perform.

        Child classes should always call ``super().setup()``.
        """
        emit.debug(f"Setting up {self.__class__.__name__}")

    @property
    def _project(self) -> Project:
        """The rendered project to use.

        This will error if the project is not yet fully configured.
        """
        return self._services.get("project").get()

    @property
    def _build_info(self) -> BuildInfo:
        """The information about the current build.

        This will error if the build plan is not configured, if the build plan contains
        multiple entries, or if the build plan is empty.
        """
        plan = self._services.get("build_plan").plan()
        match len(plan):
            case 0:
                raise errors.EmptyBuildPlanError
            case 1:
                return plan[0]
            case _:
                raise errors.MultipleBuildsError(plan)
