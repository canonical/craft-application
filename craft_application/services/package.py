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
from collections.abc import Callable, Iterator
from typing import TYPE_CHECKING, cast, final

from craft_cli import emit
from typing_extensions import deprecated

from craft_application import errors, models, util
from craft_application.services import base

if TYPE_CHECKING:  # pragma: no cover
    from craft_application.application import AppMetadata
    from craft_application.services import ServiceFactory


def package_file(path: str | pathlib.Path, partition: str | None = None) -> Callable:
    dest = pathlib.Path(path)
    if dest.is_absolute():
        raise ValueError(f"Destination must be relative, not {dest}")

    def _function_wrapper(func: Callable) -> Callable:
        func.__package_file_write_to__ = pathlib.Path(path)
        func.__partition__ = partition
        return func

    return _function_wrapper


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
        platform = self._services.get("build_plan").plan()[0].platform
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
            platform = self._services.get("build_plan").plan()[0].platform
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
    @deprecated("Use Package Files instead.")
    def metadata(self) -> models.BaseMetadata:
        """The metadata model for this project."""
        return models.BaseMetadata()

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

    def gen_artifact_names(self) -> Iterator[str]:
        """Generate the names of all the artifacts this pack will produce."""
        # Stupid hack to make this an empty generator.
        yield from ()

    def _app_needs_pack(self) -> bool:
        """App-specific override to determine whether a pack is needed.

        The default implementation of this simply returns False. However, an app may
        override this method to perform any checks it needs to determine whether the project needs a repack.

        The generic checks for package file updates and the like only run if this
        method returns False.

        :returns: False
        """
        return False

    @final
    def gen_partition_files(self, partition: str = "default"):
        """Generate the package files for the given partition."""
        for name in dir(self):
            gen = getattr(self, name)
            if callable(gen) and (
                dest := getattr(gen, "__package_file_write_to__", None)
            ):
                part_re = cast(str | None, getattr(gen, "__partition__", None))
                if part_re is not None and not re.fullmatch(part_re, partition):
                    continue
                yield (dest, gen)

    def needs_pack(self, dest: pathlib.Path) -> bool:
        if self._app_needs_pack():
            return True
        for name in self.gen_artifact_names():
            if not pathlib.Path(name).exists():
                return True
        lifecycle_service = self._services.get("lifecycle")
        if lifecycle_service.prime_state_timestamp is None:
            emit.debug("Lifecycle was never primed. Assuming we need to pack")
            return True
        for name in self.gen_artifact_names():
            artifact_path = dest / name
            if not artifact_path.exists():
                emit.debug(f"Needs pack because file doesn't exist: '{name}'")
                return True
            if lifecycle_service.prime_state_timestamp > artifact_path.stat().st_mtime:
                emit.debug(f"Needs pack because file is older than prime state: {name}")
                return True

        for partition, partition_path in lifecycle_service.prime_dirs.items():
            if not partition_path.is_dir():
                return True
            for path, generator in self.gen_partition_files(partition or "default"):
                full_path = partition_path / path
                new_content = generator(partition)
                if full_path.exists() == (new_content is None):
                    return True
                if isinstance(new_content, str):
                    old_content = full_path.read_text()
                else:
                    old_content = full_path.read_bytes()
                if new_content != old_content:
                    return True
        return False
