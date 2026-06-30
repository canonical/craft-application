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
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, cast

from craft_cli import emit

from craft_application import errors, models, util
from craft_application.services import base

if TYPE_CHECKING:  # pragma: no cover
    from craft_application.application import AppMetadata
    from craft_application.services import ServiceFactory


@dataclass(frozen=True)
class PackageFileEntry:
    """Metadata about a generated package file."""

    relative_path: pathlib.PurePosixPath
    method_name: str
    partition_re: str | None = None


def package_file(
    relative_path: str | pathlib.PurePath, partition_re: str | None = None
) -> Any:
    """Register a method as the generator for a package file.

    The decorated method is discovered by :class:`PackageService` and may later be
    used by ST160-aware packers to compare and materialize generated package files.
    """

    relative_path = pathlib.PurePosixPath(relative_path)

    def decorator(method: Any) -> Any:
        setattr(
            method,
            "_craft_application_package_file",
            PackageFileEntry(
                relative_path=relative_path,
                partition_re=partition_re,
                method_name=method.__name__,
            ),
        )
        return method

    return decorator


class PackageService(base.AppService):
    """The business logic for creating packages."""

    _PACKAGE_FILE_ATTR = "_craft_application_package_file"

    def __init__(self, app: AppMetadata, services: ServiceFactory) -> None:
        super().__init__(app, services)
        self._resource_map: dict[str, pathlib.Path] | None = None

    @abc.abstractmethod
    def pack(self, prime_dir: pathlib.Path, dest: pathlib.Path) -> list[pathlib.Path]:
        """Create one or more packages.

        :param prime_dir: Directory path to the default prime directory.
            **DEPRECATED** in favour of retrieving this information from the
            :attr:`LifecycleService
            <craft_application.services.lifecycle.LifecycleService.project_info>`.
        :param dest: Directory into which to write the package(s).
        :returns: A list of paths to the created packages.
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
        artifacts: list[dict[str, str | None]] = []

        if artifact:
            artifacts.append({"name": None, "path": str(artifact)})
        if resources:
            artifacts.extend(
                {"name": name, "path": str(path)}
                for name, path in resources.items()
            )

        state_service.set("artifacts", platform, value=artifacts or None)

    def read_state(self, platform: str | None = None) -> models.PackState:
        """Read the packaging state.

        :param platform: The name of the platform to read. If not provided, uses the
            first platform in the build plan.
        :returns: A PackState object containing the artifact and resources.
        """
        if platform is None:
            platform = self._build_info.platform
        state_service = self._services.get("state")

        artifacts = cast(
            list[dict[str, str | None]] | None,
            state_service.get("artifacts", platform),
        )

        return models.PackState.unmarshal({"artifacts": artifacts or []})

    @property
    @abc.abstractmethod
    def metadata(self) -> models.BaseMetadata:
        """The metadata model for this project."""

    @property
    def supports_conditional_repack(self) -> bool:
        """Whether this service implements the ST160 package API."""
        package_cls = type(self)
        return (
            package_cls.get_artifacts is not PackageService.get_artifacts
            and package_cls._pack is not PackageService._pack
        )

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

    def get_artifacts(self) -> dict[str | None, pathlib.Path]:
        """Get the output artifacts for this application.

        Subclasses must override this to opt in to ST160 conditional repacking.
        """
        raise NotImplementedError

    def _gen_extra_assets(
        self, partition_name: str | None = None
    ) -> list[tuple[str | bytes | None | pathlib.Path, pathlib.Path]]:
        """Generate any extra assets for the given artifact/prime partition."""
        return []

    def _app_needs_repack(self, partition: str | None = None) -> bool:
        """Determine whether the application needs to repack a given artifact."""
        return False

    def _pack(self, *, name: str | None = None, path: pathlib.Path) -> None:
        """Pack a specific artifact for ST160-aware package services."""
        raise NotImplementedError

    def _extra_project_updates(self) -> bool:
        """Perform domain-specific updates to the project before packing."""
        return False

    def _package_files(
        self, partition_name: str | None = None
    ) -> list[PackageFileEntry]:
        """Return registered package-file generators for a given partition."""
        package_files: list[PackageFileEntry] = []
        package_file_indexes: dict[str, int] = {}

        for cls in reversed(type(self).__mro__):
            for value in vars(cls).values():
                entry = getattr(value, self._PACKAGE_FILE_ATTR, None)
                if entry is None:
                    continue
                if self._package_file_matches(entry, partition_name):
                    if entry.method_name in package_file_indexes:
                        package_files[package_file_indexes[entry.method_name]] = entry
                    else:
                        package_file_indexes[entry.method_name] = len(package_files)
                        package_files.append(entry)

        return package_files

    @staticmethod
    def _package_file_matches(
        entry: PackageFileEntry, partition_name: str | None
    ) -> bool:
        """Check whether a package-file entry applies to a partition."""
        if entry.partition_re is None:
            return True
        if partition_name is None:
            return False
        return re.fullmatch(entry.partition_re, partition_name) is not None
