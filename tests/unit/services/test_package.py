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

import dataclasses
from pathlib import Path

import pytest
from craft_application import errors, models
from craft_application.services import package


class FakePackageService(package.PackageService):
    def pack(self, prime_dir: Path, dest: Path) -> list[Path]:
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


def test_update_project_variable_unset(app_metadata, fake_project, fake_services):
    """Test project variables that must be set after the lifecycle runs."""
    app_metadata = dataclasses.replace(
        app_metadata,
        project_variables=["version", "color"],
        mandatory_adoptable_fields=["version", "color"],
    )

    service = FakePackageService(
        app_metadata,
        fake_services,
        project=fake_project,
    )
    service._services.lifecycle.project_info.get_project_var = lambda x: (
        "foo" if x == "version" else None
    )

    with pytest.raises(errors.PartsLifecycleError) as exc_info:
        service.update_project()

    assert str(exc_info.value) == "Project field 'color' was not set."


def test_update_project_variable_optional(
    app_metadata,
    fake_project,
    fake_services,
):
    """Test project variables that can be optionally set."""
    app_metadata = dataclasses.replace(
        app_metadata,
        project_variables=["version", "color"],
        mandatory_adoptable_fields=["version"],
    )

    service = FakePackageService(
        app_metadata,
        fake_services,
        project=fake_project,
    )
    service._services.lifecycle.project_info.get_project_var = lambda x: (
        "foo" if x == "version" else None
    )

    service.update_project()

    assert service._project.version == "foo"
