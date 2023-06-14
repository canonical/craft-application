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

import pathlib

from craft_application import models
from craft_application.services import package


class FakePackageService(package.PackageService):
    def pack(self, dest: pathlib.Path) -> list[pathlib.Path]:
        """Create a fake package."""
        raise NotImplementedError()

    @property
    def metadata(self) -> models.BaseMetadata:
        return models.BaseMetadata()


def test_write_metadata(tmp_path, app_metadata, fake_project):
    service = FakePackageService(app_metadata, fake_project)
    metadata_file = tmp_path / "metadata.yaml"
    assert not metadata_file.exists()

    service.write_metadata(tmp_path)

    assert metadata_file.is_file()
    metadata = models.BaseMetadata.from_yaml_file(metadata_file)
    assert metadata == service.metadata
