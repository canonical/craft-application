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

from typing import TYPE_CHECKING

from craft_application import models
from craft_application.services import package

if TYPE_CHECKING:  # pragma: no cover
    import pathlib


class FakePackageService(package.PackageService):
    def pack(self, prime_dir: pathlib.Path, dest: pathlib.Path) -> list[pathlib.Path]:
        """Create a fake package."""
        raise NotImplementedError

    @property
    def metadata(self) -> models.BaseMetadata:
        return models.BaseMetadata()


def test_write_metadata(tmp_path, app_metadata, fake_project, fake_services):
    service = FakePackageService(app_metadata, fake_services, project=fake_project)
    metadata_file = tmp_path / "metadata.yaml"
    assert not metadata_file.exists()

    service.write_metadata(tmp_path)

    assert metadata_file.is_file()
    metadata = models.BaseMetadata.from_yaml_file(metadata_file)
    assert metadata == service.metadata
