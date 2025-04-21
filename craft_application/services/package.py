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
from typing import TYPE_CHECKING

from craft_cli import emit

from craft_application import errors, models, util
from craft_application.services import base

if TYPE_CHECKING:  # pragma: no cover
    import pathlib

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

    def write_state(self, artifact: pathlib.Path | None, resources: dict[str, pathlib.Path] | None) -> None:
        """Write the packaging state."""
        path = util.get_managed_pack_state_path(self._app)
        pack_state = models.PackState(artifact=artifact, resources=resources)
        pack_state.to_yaml_file(path)

    def read_state(self) -> models.PackState:
        """Read the packaging state."""
        path = util.get_managed_pack_state_path(self._app)
        with path.open() as f:
            data = util.safe_yaml_load(f)
        return models.PackState.unmarshal(data)

    @property
    @abc.abstractmethod
    def metadata(self) -> models.BaseMetadata:
        """The metadata model for this project."""

    def update_project(self) -> None:
        """Update project fields with dynamic values set during the lifecycle."""
        update_vars: dict[str, str] = {}
        project_info = self._services.lifecycle.project_info
        for var in self._app.project_variables:
            update_vars[var] = project_info.get_project_var(var)

        emit.debug(f"Update project variables: {update_vars}")
        project = self._services.get("project").get()
        project.__dict__.update(update_vars)

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
