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

if typing.TYPE_CHECKING:
    from craft_application import models
    from craft_application.application import AppMetadata
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
        """Application-specific service setup."""
        emit.debug(f"Setting up {self.__class__.__name__}")


class ProjectService(AppService, metaclass=abc.ABCMeta):
    """A service that requires access to a project.

    The ServiceFactory will refuse to instantiate a subclass of this service if
    no project can be created or the project is invalid.
    """

    def __init__(
        self,
        app: AppMetadata,
        services: ServiceFactory,
        *,
        project: models.Project,
    ) -> None:
        super().__init__(app=app, services=services)
        self._project = project
