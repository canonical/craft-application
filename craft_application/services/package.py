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
    from collections.abc import Mapping

    from craft_application.application import AppMetadata
    from craft_application.services import ServiceFactory


_PACKAGE_FILE_ATTR = "_craft_application_package_file"
_DEFAULT_ARTIFACT_NAME = "default"


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
            _PACKAGE_FILE_ATTR,
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

    def __init__(self, app: AppMetadata, services: ServiceFactory) -> None:
        super().__init__(app, services)
        self._resource_map: dict[str, pathlib.Path] | None = None
        self._output_dir = pathlib.Path()

    def pack(self, prime_dir: pathlib.Path, dest: pathlib.Path) -> list[pathlib.Path]:
        """Create one or more packages.

        :param prime_dir: Directory path to the default prime directory.
            **DEPRECATED** in favour of retrieving this information from the
            :attr:`LifecycleService
            <craft_application.services.lifecycle.LifecycleService.project_info>`.
        :param dest: Directory into which to write the package(s).
        :returns: A list of paths to the created packages.
        """
        raise NotImplementedError

    # This was implemented as a separate property to allow applications to
    # retrieve this information without changing the pack method to also
    # return the resource mapping. The two calls can be consolidated in the
    # next API change.
    @property
    def resource_map(self) -> dict[str, pathlib.Path] | None:
        """Map resource name to artifact file name."""
        return self._resource_map

    @property
    def output_dir(self) -> pathlib.Path:
        """The requested output directory for the current pack operation."""
        return self._output_dir

    def set_output_dir(self, path: pathlib.Path) -> None:
        """Set the output directory for the current pack operation."""
        self._output_dir = path

    def write_state(
        self, artifact: pathlib.Path | None, resources: dict[str, pathlib.Path] | None
    ) -> None:
        """Write the packaging state."""
        artifacts: dict[str | None, pathlib.Path] = {}
        if artifact:
            artifacts[None] = artifact
        if resources:
            artifacts.update(resources)

        self.write_artifacts_state(artifacts)

    def write_artifacts_state(
        self, artifacts: Mapping[str | None, pathlib.Path]
    ) -> None:
        """Write artifact-oriented packaging state."""
        platform = self._build_info.platform
        state_service = self._services.get("state")
        state_entries = [
            {"name": name, "path": str(path)} for name, path in artifacts.items()
        ]

        state_service.set("artifacts", platform, value=state_entries or None)

    def read_state(self, platform: str | None = None) -> models.PackState:
        """Read the packaging state.

        :param platform: The name of the platform to read. If not provided, uses the
            first platform in the build plan.
        :returns: A PackState object containing the artifact and resources.
        """
        if platform is None:
            platform = self._build_info.platform
        state_service = self._services.get("state")

        # Consumers still use PackState's artifact/resources compatibility views
        # while the storage format moves toward an all-artifacts model without
        # the old artifact/resource split, in line with applications where there's
        # no distinction between the generated packages such as Debcraft. This
        # should be changed in the future to use only artifacts.
        try:
            artifacts = cast(
                list[dict[str, str | None]] | None,
                state_service.get("artifacts", platform),
            )
        except KeyError:
            artifact = cast(str | None, state_service.get("artifact", platform))
            resources = cast(
                dict[str, str] | None, state_service.get("resources", platform)
            )
            artifact_entries: list[dict[str, str | None]] = []
            if artifact:
                artifact_entries.append({"name": None, "path": artifact})
            if resources:
                artifact_entries.extend(
                    {"name": name, "path": path} for name, path in resources.items()
                )
            artifacts = artifact_entries

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

    def needs_packing(self, partition: str | None = None) -> bool:
        """Determine whether the given artifact/partition requires packing."""
        if self._app.always_repack:
            return True

        lifecycle = self._services.get("lifecycle")
        if lifecycle.requires_repack:
            return True

        artifact_path = self.get_artifacts()[partition]
        if not artifact_path.is_file():
            return True

        for file in self._package_files(partition):
            if self._package_file_changed(file, partition):
                return True

        for source, destination in self._gen_extra_assets(partition):
            if self._asset_changed(source, destination, partition):
                return True

        return self._app_needs_repack(partition)

    def pack_artifacts(self) -> Mapping[str | None, bool]:
        """Pack all necessary artifacts for an ST160-aware package service."""
        artifacts = self.get_artifacts()
        packed: dict[str | None, bool] = {}

        for name, path in artifacts.items():
            if not self.needs_packing(name):
                packed[name] = False
                continue

            self._materialize_package_files(name)
            self._materialize_extra_assets(name)
            self._pack(name=name, path=path)
            packed[name] = True

        return packed

    def _package_files(
        self, partition_name: str | None = None
    ) -> list[PackageFileEntry]:
        """Return registered package-file generators for a given partition."""
        package_files: list[PackageFileEntry] = []
        package_file_indexes: dict[str, int] = {}

        for cls in reversed(type(self).__mro__):
            for value in vars(cls).values():
                entry = getattr(value, _PACKAGE_FILE_ATTR, None)
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
        normalized_partition = "default" if partition_name is None else partition_name
        return re.fullmatch(entry.partition_re, normalized_partition) is not None

    def _prime_dir_for(self, partition_name: str | None) -> pathlib.Path:
        """Return the prime directory corresponding to an artifact partition."""
        lifecycle = self._services.get("lifecycle")
        if partition_name in (None, "default"):
            return lifecycle.prime_dir
        return lifecycle.project_info.dirs.get_prime_dir(partition_name)

    @staticmethod
    def _partition_key(partition_name: str | None) -> str:
        """Normalize artifact/partition names for internal lookups."""
        return _DEFAULT_ARTIFACT_NAME if partition_name is None else partition_name

    def _package_file_changed(
        self, package_file: PackageFileEntry, partition_name: str | None
    ) -> bool:
        """Return whether a generated package file differs from prime contents."""
        generator = getattr(self, package_file.method_name)
        content = generator(partition_name)
        if content is False:
            return False

        destination = self._prime_dir_for(partition_name) / package_file.relative_path
        return self._asset_changed(content, destination, partition_name)

    def _asset_changed(
        self,
        source: str | bytes | None | pathlib.Path,
        destination: pathlib.Path,
        partition_name: str | None,
    ) -> bool:
        """Return whether a package file or extra asset differs from prime contents."""
        del partition_name
        if isinstance(source, pathlib.Path):
            if not destination.exists():
                return True
            return source.stat().st_mtime_ns > destination.stat().st_mtime_ns

        if source is None:
            return destination.exists()

        if not destination.is_file():
            return True

        expected = source.encode() if isinstance(source, str) else source
        return destination.read_bytes() != expected

    def _materialize_package_files(self, partition_name: str | None) -> None:
        """Write generated package files for a specific artifact partition."""
        prime_dir = self._prime_dir_for(partition_name)

        for package_file in self._package_files(partition_name):
            generator = getattr(self, package_file.method_name)
            content = generator(partition_name)
            if content is False:
                continue

            destination = prime_dir / package_file.relative_path
            self._write_asset(content, destination)

    def _materialize_extra_assets(self, partition_name: str | None) -> None:
        """Write extra assets for a specific artifact partition."""
        for source, destination in self._gen_extra_assets(partition_name):
            self._write_asset(source, destination)

    def _write_asset(
        self, source: str | bytes | None | pathlib.Path, destination: pathlib.Path
    ) -> None:
        """Write a generated package file or extra asset into prime."""
        if source is None:
            destination.unlink(missing_ok=True)
            return

        destination.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(source, pathlib.Path):
            destination.write_bytes(source.read_bytes())
            return
        if isinstance(source, str):
            destination.write_text(source)
            return
        destination.write_bytes(source)
