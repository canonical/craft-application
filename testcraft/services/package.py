# This file is part of craft_application.
#
# Copyright 2025 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Testcraft package service."""

import pathlib
import tarfile

import craft_application
from craft_application.services import package

from testcraft.models.metadata import Metadata


class PackageService(package.PackageService):
    """Package service for testcraft."""

    @property
    def metadata(self) -> Metadata:
        """Get the metadata for this model."""
        if self._project.version is None:
            raise ValueError("Unknown version")
        return Metadata(
            name=self._project.name,
            version=self._project.version,
            craft_application_version=craft_application.__version__,
        )

    def pack(self, prime_dir: pathlib.Path, dest: pathlib.Path) -> list[pathlib.Path]:
        """Pack a testcraft artifact."""
        project = self._project
        platform = self._build_info.platform
        tarball_name = f"{project.name}-{project.version}-{platform}.testcraft"
        with tarfile.open(dest / tarball_name, mode="w:xz") as tar:
            tar.add(prime_dir, arcname=".")
        return [dest / tarball_name]
