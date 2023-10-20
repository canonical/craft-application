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

from craft_application import errors, models

if typing.TYPE_CHECKING:
    from craft_application.application import AppMetadata
    from craft_application.services import ServiceFactory


# ignoring the fact that this abstract class has no abstract methods.
class BaseService(metaclass=abc.ABCMeta):  # noqa: B024
    """Abstract base class for a service. Should not be used directly.

    BaseService allows lazy-loading of a project. EagerService should be used
    for services that always require a project on load.
    """

    def __init__(
        self,
        app: AppMetadata,
        services: ServiceFactory,
        *,
        project_getter: typing.Callable[[], models.Project],
    ) -> None:
        self._app = app
        self._services = services
        self._project: models.Project | None = None
        self._project_getter = project_getter

    def setup(self) -> None:
        """Application-specific service preparation."""
        emit.debug("setting up service")

    def _get_project(self) -> models.Project:
        """Get the project for this app run.

        returns: a project model
        raises: CraftError if the project cannot be loaded.

        Caches the project in self._project otherwise.
        """
        if self._project is None:
            try:
                self._project = self._project_getter()
            # Intentionally catching a broad exception to provide a more useful error.
            except Exception as exc:  # noqa: BLE001
                raise errors.CraftError(
                    "Project could not be loaded.", details=str(exc)
                ) from exc
        return self._project


# ignoring the fact that this abstract class has no abstract methods.
class ProjectService(BaseService, metaclass=abc.ABCMeta):
    """A service that requires the project from startup."""

    _project: models.Project

    def __init__(
        self,
        app: AppMetadata,
        services: ServiceFactory,
        *,
        project: models.Project,
    ) -> None:
        super().__init__(app, services, project_getter=lambda: project)
        self._project = project
