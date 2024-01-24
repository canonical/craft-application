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

from craft_application.services import base

if TYPE_CHECKING:  # pragma: no cover
    import pathlib

    from craft_application import models

from pathlib import Path
from typing import Any

from craft_archives import repo  # type: ignore[import-untyped]
from craft_cli import emit
from craft_parts import (
    LifecycleManager,
    ProjectInfo,
)


class PackageService(base.ProjectService):
    """Business logic for creating packages."""

    @abc.abstractmethod
    def pack(self, prime_dir: pathlib.Path, dest: pathlib.Path) -> list[pathlib.Path]:
        """Create one or more packages as appropriate.

        :param prime_dir: Directory path to the prime directory.
        :param dest: Directory into which to write the package(s).
        :returns: A list of paths to created packages.
        """

    @property
    @abc.abstractmethod
    def metadata(self) -> models.BaseMetadata:
        """The metadata model for this project."""

    def write_metadata(self, path: pathlib.Path) -> None:
        """Write the project metadata to metadata.yaml in the given directory.

        :param path: The path to the prime directory.
        """
        path.mkdir(parents=True, exist_ok=True)
        self.metadata.to_yaml_file(path / "metadata.yaml")


class RepositoryService(base.ProjectService):
    """Business logic for managing repositories."""

    @classmethod
    def install_package_repositories(
        cls,
        package_repositories: list[dict[str, Any]] | None,
        lifecycle_manager: LifecycleManager,
    ) -> None:
        """Install package repositories in the environment."""
        if not package_repositories:
            emit.debug("No package repositories specified, none to install.")
            return

        refresh_required = repo.install(
            package_repositories, key_assets=Path("/dev/null")
        )
        if refresh_required:
            emit.progress("Refreshing repositories")
            lifecycle_manager.refresh_packages_list()

        emit.progress("Package repositories installed")

    @classmethod
    def install_overlay_repositories(
        cls, overlay_dir: Path, project_info: ProjectInfo
    ) -> None:
        """Install overlay repositories in the environment."""
        if project_info.base != "bare":
            package_repositories = project_info.package_repositories
            repo.install_in_root(
                project_repositories=package_repositories,
                root=overlay_dir,
                key_assets=Path("/dev/null"),
            )
