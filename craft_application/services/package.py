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
"""Service class for lifecycle commands."""

from __future__ import annotations

import abc
import pathlib
from typing import TYPE_CHECKING, cast

from craft_cli import emit

from craft_application import errors, models, util
from craft_application.services import base

if TYPE_CHECKING:  # pragma: no cover
    from craft_application.application import AppMetadata
    from craft_application.services import ServiceFactory


class PackageService(base.AppService):
    """Business logic for creating packages."""

    def __init__(self, app: AppMetadata, services: ServiceFactory) -> None:
        super().__init__(app, services)
        self._resource_map: dict[str, pathlib.Path] | None = None

    @abc.abstractmethod
    def pack(self, prime_dir: pathlib.Path, dest: pathlib.Path) -> list[pathlib.Path]:
        """Create one or more packages as appropriate.

        :param prime_dir: Directory path to the prime directory.
        :param dest: Directory into which to write the package(s).
        :returns: A list of paths to created packages.
        """

    # This was implemented as a separate property to allow applications to
    # retrieve this information without changing the pack method to also
    # return the resource mapping. The two calls can be consolidated in the
    # next API change.
    @property
    def resource_map(self) -> dict[str, pathlib.Path] | None:
        """Map resource name to artifact file name."""
        return self._resource_map

    def write_state(
        self, artifact: pathlib.Path | None, resources: dict[str, pathlib.Path] | None
    ) -> None:
        """Write the packaging state."""
        platform = self._build_info.platform
        state_service = self._services.get("state")

        state_service.set(
            "artifact", platform, value=str(artifact) if artifact else None
        )
        state_service.set(
            "resources",
            platform,
            value={k: str(v) for k, v in resources.items()} if resources else None,
        )

    def read_state(self, platform: str | None = None) -> models.PackState:
        """Read the packaging state.

        :param platform: The name of the platform to read. If not provided, uses the
            first platform in the build plan.
        :returns: A PackState object containing the artifact and resources.
        """
        if platform is None:
            platform = self._build_info.platform
        state_service = self._services.get("state")

        artifact = cast(str | None, state_service.get("artifact", platform))
        resources = cast(
            dict[str, str] | None, state_service.get("resources", platform)
        )
        return models.PackState(
            artifact=pathlib.Path(artifact) if artifact else None,
            resources={k: pathlib.Path(v) for k, v in resources.items()}
            if resources
            else None,
        )

    @property
    @abc.abstractmethod
    def metadata(self) -> models.BaseMetadata:
        """The metadata model for this project."""

    def update_project(self) -> None:
        """Update project fields with dynamic values set during the lifecycle."""
        project_info = self._services.get("lifecycle").project_info
        update_vars = project_info.project_vars.marshal("value")
        emit.debug(f"Project variable updates: {update_vars}")

        project_service = self._services.get("project")
        project_service.deep_update(update_vars)
        project = project_service.get()

        # Give subclasses a chance to update the project with their own logic
        self._extra_project_updates()

        unset_fields = [
            field
            for field in self._app.mandatory_adoptable_fields
            if not getattr(project, field)
        ]

        if unset_fields:
            fields = util.humanize_list(unset_fields, "and", sort=False)
            raise errors.PartsLifecycleError(
                f"Project fields {fields} were not set."
                if len(unset_fields) > 1
                else f"Project field {fields} was not set."
            )

    def write_metadata(self, path: pathlib.Path) -> None:
        """Write the project metadata to metadata.yaml in the given directory.

        :param path: The path to the prime directory.
        """
        path.mkdir(parents=True, exist_ok=True)
        self.metadata.to_yaml_file(path / "metadata.yaml")

    def _extra_project_updates(self) -> None:
        """Perform domain-specific updates to the project before packing."""
