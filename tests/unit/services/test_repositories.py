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
"""Tests for PackageService."""
from __future__ import annotations

from pathlib import Path

from craft_application.util import repositories


def test_repo_install_package_repositories(emitter, mocker, lifecycle_service):
    package_repositories = [{"type": "apt", "ppa": "ppa/ppa"}]

    repo_install = mocker.patch("craft_archives.repo.install", return_value=False)

    repositories.install_package_repositories(
        package_repositories, lifecycle_service._lcm
    )

    repo_install.assert_called_once_with(
        package_repositories, key_assets=Path("/dev/null")
    )

    emitter.assert_progress("Package repositories installed")


def test_repo_install_package_repositories_empty(emitter, mocker, lifecycle_service):
    package_repositories = None

    repo_install = mocker.patch("craft_archives.repo.install", return_value=False)

    repositories.install_package_repositories(
        package_repositories, lifecycle_service._lcm
    )

    repo_install.assert_not_called()

    emitter.assert_debug("No package repositories specified, none to install.")


def test_repo_install_package_repositories_refresh(emitter, mocker, lifecycle_service):
    package_repositories = [{"type": "apt", "ppa": "ppa/ppa"}]

    repo_install = mocker.patch("craft_archives.repo.install", return_value=True)
    lcm_refresh = mocker.patch(
        "craft_parts.lifecycle_manager.LifecycleManager.refresh_packages_list"
    )

    repositories.install_package_repositories(
        package_repositories, lifecycle_service._lcm
    )

    repo_install.assert_called_once_with(
        package_repositories, key_assets=Path("/dev/null")
    )

    lcm_refresh.assert_called_once()

    emitter.assert_progress("Refreshing repositories")
    emitter.assert_progress("Package repositories installed")


def test_repo_install_overlay_repositories(tmp_path, mocker, lifecycle_service):
    package_repositories = [{"type": "apt", "ppa": "ppa/ppa"}]
    overlay_dir = tmp_path / "overlay"
    project_info = lifecycle_service._lcm._project_info

    lifecycle_service._lcm._project_info.package_repositories = package_repositories

    repo_install = mocker.patch("craft_archives.repo.install_in_root")

    repositories.install_overlay_repositories(overlay_dir, project_info)

    repo_install.assert_called_once_with(
        project_repositories=package_repositories,
        root=overlay_dir,
        key_assets=Path("/dev/null"),
    )


def test_repo_install_overlay_repositories_empty(tmp_path, mocker, lifecycle_service):
    package_repositories = []
    overlay_dir = tmp_path / "overlay"
    project_info = lifecycle_service._lcm._project_info

    lifecycle_service._lcm._project_info.package_repositories = package_repositories

    repo_install = mocker.patch("craft_archives.repo.install_in_root")

    repositories.install_overlay_repositories(overlay_dir, project_info)

    repo_install.assert_not_called()
