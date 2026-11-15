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
import hashlib
import json
import pathlib
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, TypeVar, cast

from craft_cli import emit

from craft_application import errors, models, util
from craft_application.services import base, state

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Mapping

    from craft_application.application import AppMetadata
    from craft_application.services import ServiceFactory


_PACKAGE_FILE_ATTR = "_craft_application_package_file"


def _rel_to_prime(dest: pathlib.Path, prime_dir: pathlib.Path) -> str | None:
    """Return ``dest`` relative to prime, or None if it is not inside prime."""
    try:
        rel = dest.relative_to(prime_dir)
    except ValueError:
        return None
    return rel.as_posix() if ".." not in rel.parts else None


def _sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


_MethodT = TypeVar("_MethodT", bound=Callable[..., Any])


@dataclass(frozen=True)
class PackageFileEntry:
    """Metadata about a generated package file."""

    relative_path: pathlib.PurePosixPath
    method_name: str
    partition_re: str | None = None


def package_file(
    relative_path: str | pathlib.PurePath, partition_re: str | None = None
) -> Callable[[_MethodT], _MethodT]:
    """Register a method as the generator for a package file.

    The decorated method is discovered by :class:`PackageService` and may later be
    used by packers to compare and materialize generated package files.
    """
    relative_path = pathlib.PurePosixPath(relative_path)
    if relative_path.is_absolute():
        raise ValueError(
            f"Package file path must be relative: {relative_path.as_posix()!r}"
        )
    if ".." in relative_path.parts:
        raise ValueError(
            "Package file path must not contain parent directory traversals: "
            f"{relative_path.as_posix()!r}"
        )

    def decorator(method: _MethodT) -> _MethodT:
        setattr(
            method,
            _PACKAGE_FILE_ATTR,
            PackageFileEntry(
                relative_path=relative_path,
                partition_re=partition_re,
                method_name=method.__name__,  # ty: ignore[missing-attribute]
            ),
        )
        return method

    return decorator


class PackageService(base.AppService):
    """The business logic for creating packages."""

    _package_file_registry: list[PackageFileEntry] = []

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        # Build registry: start with the parent's entries, then overlay this class's.
        registry = list(cls._package_file_registry)
        indexes = {entry.method_name: i for i, entry in enumerate(registry)}

        for value in vars(cls).values():
            entry = getattr(value, _PACKAGE_FILE_ATTR, None)
            if entry is None:
                continue
            if entry.method_name in indexes:
                registry[indexes[entry.method_name]] = entry
            else:
                indexes[entry.method_name] = len(registry)
                registry.append(entry)

        cls._package_file_registry = registry

    def __init__(self, app: AppMetadata, services: ServiceFactory) -> None:
        super().__init__(app, services)
        self._resource_map: dict[str, pathlib.Path] | None = None
        self._output_dir = pathlib.Path()
        self._project_was_updated = False

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
        state_entries: list[dict[str, state.ValueType]] = [
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
        """Whether this service implements the metadata mediation API."""
        package_cls = type(self)
        return (
            package_cls.get_artifacts is not PackageService.get_artifacts
            and package_cls._pack is not PackageService._pack  # noqa: SLF001
        )

    def update_project(self) -> None:
        """Update project fields with dynamic values set during the lifecycle."""
        self._project_was_updated = False
        project_info = self._services.get("lifecycle").project_info
        update_vars = project_info.project_vars.marshal("value")
        emit.debug(f"Project variable updates: {update_vars}")

        project_service = self._services.get("project")
        project_service.deep_update(update_vars)
        project = project_service.get()

        # Give subclasses a chance to update the project with their own logic
        self._project_was_updated = self._extra_project_updates()

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

        Subclasses must override this to opt in to conditional repacking.
        """
        raise NotImplementedError

    def _gen_extra_assets(
        self,
        partition_name: str | None = None,  # noqa: ARG002
    ) -> list[tuple[str | bytes | None | pathlib.Path, pathlib.Path]]:
        """Generate any extra assets for the given artifact/prime partition."""
        return []

    def _app_needs_repack(self, partition: str | None = None) -> bool:  # noqa: ARG002
        """Determine whether the application needs to repack a given artifact."""
        return False

    def _pack(self, *, name: str | None = None, path: pathlib.Path) -> None:
        """Pack a specific artifact for package services with mediated metadata."""
        raise NotImplementedError

    def _extra_project_updates(self) -> bool:
        """Perform domain-specific updates to the project before packing."""
        return False

    def _mediation_record_path(self, partition: str | None) -> pathlib.Path:
        """Return the path to the mediation record file for a partition."""
        lifecycle = self._services.get("lifecycle")
        work_dir = lifecycle.project_info.dirs.work_dir
        partition_name = "default" if partition is None else partition
        return work_dir / "package-state" / f"{partition_name}.json"

    def _load_mediation_record(self, partition: str | None) -> dict[str, Any]:
        """Load the mediation record for a partition from the work directory.

        ``mediated`` maps each prime-relative path we wrote to its sha256.
        ``packed`` lists the mediated files in the last packed artifact, not
        every file in the artifact.
        """
        path = self._mediation_record_path(partition)
        if not path.is_file():
            return {"mediated": {}, "packed": []}
        try:
            data = json.loads(path.read_text())
            if isinstance(data, dict):
                mediated = data.get("mediated")
                packed = data.get("packed")
                if isinstance(mediated, dict) and isinstance(packed, list):
                    return {"mediated": mediated, "packed": packed}
        except (OSError, json.JSONDecodeError):
            emit.debug(f"Could not load mediation record from {path!s}")
        return {"mediated": {}, "packed": []}

    def _save_mediation_record(
        self, record: dict[str, Any], partition: str | None
    ) -> None:
        """Save the mediation record for a partition to the work directory."""
        path = self._mediation_record_path(partition)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record))

    def _current_mediated(self, partition: str | None) -> set[str]:
        """Return the prime-relative paths of files mediated in this run.

        This calls the package file generators.
        """
        prime_dir = self._prime_dir_for(partition)
        dests = [
            prime_dir / entry.relative_path
            for entry in self._package_files(partition)
            if getattr(self, entry.method_name)(partition) not in (False, None)
        ]
        dests.extend(
            dest
            for source, dest in self._gen_extra_assets(partition)
            if source is not None
        )
        return {rel for dest in dests if (rel := _rel_to_prime(dest, prime_dir))}

    def _stale_mediated(
        self, record: dict[str, Any], current: set[str], partition: str | None
    ) -> tuple[set[str], set[str]]:
        """Split recorded files that are no longer mediated.

        Returns (ours, changed): stale files still holding the content we wrote,
        and stale files that are gone or were changed by something else.
        """
        prime_dir = self._prime_dir_for(partition)
        ours: set[str] = set()
        changed: set[str] = set()
        for rel in set(record["mediated"]) - current:
            dest = prime_dir / rel
            if dest.is_file() and _sha256(dest) == record["mediated"][rel]:
                ours.add(rel)
            else:
                changed.add(rel)
        return ours, changed

    def _remove_stale_mediated(self, partition: str | None, current: set[str]) -> None:
        """Delete files we mediated earlier that are no longer generated.

        A file is only deleted if it still has the content we wrote. Otherwise
        another component changed it, so it is kept and dropped from the record.
        """
        record = self._load_mediation_record(partition)
        ours, changed = self._stale_mediated(record, current, partition)
        prime_dir = self._prime_dir_for(partition)
        for rel in ours:
            self._write_asset(None, prime_dir / rel)
        for rel in changed:
            if (prime_dir / rel).exists():
                emit.debug(
                    f"Keeping {prime_dir / rel}: it changed after it was written."
                )
        for rel in ours | changed:
            del record["mediated"][rel]
        self._save_mediation_record(record, partition)

    def needs_packing(self, partition: str | None = None) -> bool:
        """Determine whether the given artifact/partition requires packing."""
        if not self._project.parts:
            emit.debug("No parts to pack, skipping.")
            return False
        lifecycle = self._services.get("lifecycle")
        if (
            self._app.always_repack
            or lifecycle.requires_repack
            or self._project_was_updated
        ):
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

        return self._mediation_stale(partition) or self._app_needs_repack(partition)

    def _mediation_stale(self, partition: str | None) -> bool:
        """Whether a file we packed or wrote earlier is no longer generated."""
        if not self.supports_conditional_repack:
            return False
        record = self._load_mediation_record(partition)
        if not (record["packed"] or record["mediated"]):
            return False
        current = self._current_mediated(partition)
        if set(record["packed"]) - current:
            return True
        ours, _ = self._stale_mediated(record, current, partition)
        return bool(ours)

    def pack_artifacts(self) -> Mapping[str | None, bool]:
        """Pack all artifacts for a package service with mediated metadata."""
        artifacts = self.get_artifacts()
        packed: dict[str | None, bool] = {}

        for name, path in artifacts.items():
            if not self.needs_packing(name):
                packed[name] = False
                continue

            current = (
                self._current_mediated(name)
                if self.supports_conditional_repack
                else None
            )
            if current is not None:
                self._remove_stale_mediated(name, current)

            self._materialize_package_files(name)
            self._materialize_extra_assets(name)
            self._pack(name=name, path=path)

            if current is not None:
                record = self._load_mediation_record(name)
                record["packed"] = sorted(current)
                self._save_mediation_record(record, name)

            packed[name] = True

        return packed

    def _package_files(
        self, partition_name: str | None = None
    ) -> list[PackageFileEntry]:
        """Return registered package-file generators for a given partition."""
        return [
            entry
            for entry in self._package_file_registry
            if self._package_file_matches(entry, partition_name)
        ]

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
        partition_name: str | None,  # noqa: ARG002
    ) -> bool:
        """Return whether a package file or extra asset differs from prime contents."""
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
            self._mediate(content, destination, partition_name)

    def _materialize_extra_assets(self, partition_name: str | None) -> None:
        """Write extra assets for a specific artifact partition."""
        for source, destination in self._gen_extra_assets(partition_name):
            self._mediate(source, destination, partition_name)

    def _mediate(
        self,
        source: str | bytes | None | pathlib.Path,
        destination: pathlib.Path,
        partition_name: str | None = None,
    ) -> None:
        """Write or delete an asset and update the mediation record.

        Do not override this method. Subclasses should override _write_asset instead.
        """
        self._write_asset(source, destination)
        if not self.supports_conditional_repack:
            return

        rel_path = _rel_to_prime(destination, self._prime_dir_for(partition_name))
        if rel_path is None:
            return  # Only files inside prime are tracked and cleaned up.

        record = self._load_mediation_record(partition_name)
        if destination.is_file():
            record["mediated"][rel_path] = _sha256(destination)
        else:
            record["mediated"].pop(rel_path, None)

        self._save_mediation_record(record, partition_name)

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
