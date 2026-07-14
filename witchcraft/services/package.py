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
"""Witchcraft package service."""

import pathlib
import tarfile
from typing import cast

import craft_application
from craft_application.services import package

from witchcraft.models.metadata import ComponentMetadata, Metadata
from witchcraft.models.project import Component, Project


class PackageService(package.PackageService):
    """Package service for witchcraft."""

    @package.package_file("witchcraft-metadata.yaml")
    def _witchcraft_metadata(self, partition: str | None = None) -> str:
        """Generate a package-managed metadata file for ST160 testing."""
        if partition is not None:
            raise ValueError(f"Unexpected witchcraft partition: {partition}")
        return self.metadata.to_yaml_string()

    @property
    def metadata(self) -> Metadata:
        """Get the metadata for this model."""
        if self._project.version is None:
            raise ValueError("Unknown version")

        components = self._process_components(cast("Project", self._project).components)

        return Metadata(
            name=self._project.name,
            version=self._project.version,
            craft_application_version=craft_application.__version__,
            components=components,
        )

    def get_artifacts(self) -> dict[str | None, pathlib.Path]:
        """Get the witchcraft artifact to pack."""
        project = self._project
        platform = self._build_info.platform
        tarball_name = f"{project.name}-{project.version}-{platform}.witchcraft"
        return {None: self.output_dir / tarball_name}

    def _pack(self, *, name: str | None = None, path: pathlib.Path) -> None:
        """Pack a witchcraft artifact."""
        if name is not None:
            raise ValueError(f"Unexpected witchcraft artifact name: {name}")

        with tarfile.open(path, mode="w:xz") as tar:
            tar.add(self._services.get("lifecycle").prime_dir, arcname=".")

    def _process_components(
        self,
        components: dict[str, Component] | None,
    ) -> dict[str, ComponentMetadata] | None:
        """Convert Components from a project to ComponentMetadata.

        :param components: Component data from a project model.

        :returns: A dictionary of ComponentMetadata or None if no components are defined.
        """
        if not components:
            return None

        return {
            name: ComponentMetadata.from_component(data)
            for name, data in components.items()
        }
