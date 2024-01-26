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
"""Package repositories related functions."""

from __future__ import annotations

from pathlib import Path

from craft_archives import repo  # type: ignore[import-untyped]
from craft_archives.repo.package_repository import (  # type: ignore[import-untyped]
    PackageRepositoryApt,
    PackageRepositoryAptPPA,
    PackageRepositoryAptUCA,
)
from craft_cli import emit
from craft_parts import (
    LifecycleManager,
    ProjectInfo,
)


def install_package_repositories(
    package_repositories: list[
        PackageRepositoryApt | PackageRepositoryAptPPA | PackageRepositoryAptUCA
    ]
    | None,
    lifecycle_manager: LifecycleManager,
) -> None:
    """Install package repositories in the environment."""
    if not package_repositories:
        emit.debug("No package repositories specified, none to install.")
        return

    repos = [repo.marshal() for repo in package_repositories]
    refresh_required = repo.install(repos, key_assets=Path("/dev/null"))
    if refresh_required:
        emit.progress("Refreshing repositories")
        lifecycle_manager.refresh_packages_list()

    emit.progress("Package repositories installed")


def install_overlay_repositories(overlay_dir: Path, project_info: ProjectInfo) -> None:
    """Install overlay repositories in the environment."""
    if not project_info.package_repositories:
        emit.debug("No package repositories specified, none to install.")
        return
    repos = [repo.marshal() for repo in project_info.package_repositories]
    if repos:
        repo.install_in_root(
            project_repositories=repos,
            root=overlay_dir,
            key_assets=Path("/dev/null"),
        )
