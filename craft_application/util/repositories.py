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
from typing import Any

from craft_cli import emit
from craft_parts import (
    LifecycleManager,
    ProjectInfo,
)


def install_package_repositories(
    package_repositories: list[dict[str, Any]] | None,
    lifecycle_manager: LifecycleManager,
) -> None:
    """Install package repositories in the environment."""
    from craft_archives import repo  # type: ignore[import-untyped]

    if not package_repositories:
        emit.debug("No package repositories specified, none to install.")
        return

    refresh_required = repo.install(package_repositories, key_assets=Path("/dev/null"))
    if refresh_required:
        emit.progress("Refreshing repositories")
        lifecycle_manager.refresh_packages_list()

    emit.progress("Package repositories installed")


def install_overlay_repositories(overlay_dir: Path, project_info: ProjectInfo) -> None:
    """Install overlay repositories in the environment."""
    from craft_archives import repo  # type: ignore[import-untyped]

    package_repositories = project_info.package_repositories
    if package_repositories:
        repo.install_in_root(
            project_repositories=package_repositories,
            root=overlay_dir,
            key_assets=Path("/dev/null"),
        )
