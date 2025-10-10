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

import pytest
from craft_application import errors, models, util
from craft_application.services import package

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def fake_project_dict(request, fake_project_yaml: str):
    """Drop fields and add adopt-info to the project file."""
    data = util.safe_yaml_load(fake_project_yaml)
    data["adopt-info"] = "part1"

    # delete fields from project
    for field in getattr(request, "param", []):
        data.pop(field, None)

    return data


class FakePackageService(package.PackageService):
    def pack(self, prime_dir: Path, dest: Path) -> list[Path]:
        """Create a fake package."""
        raise NotImplementedError

    @property
    def metadata(self) -> models.BaseMetadata:
        return models.BaseMetadata()


def test_write_metadata(tmp_path, app_metadata, fake_project, fake_services):
    service = FakePackageService(app_metadata, fake_services)
    metadata_file = tmp_path / "metadata.yaml"
    assert not metadata_file.exists()

    service.write_metadata(tmp_path)

    assert metadata_file.is_file()
    metadata = models.BaseMetadata.from_yaml_file(metadata_file)
    assert metadata == service.metadata


@pytest.mark.parametrize(
    ("app_metadata", "fake_project_dict", "result"),
    [
        (
            {
                "project_variables": ["version", "contact"],
                "mandatory_adoptable_fields": ["version", "contact"],
            },
            ["contact"],
            "Project field 'contact' was not set.",
        ),
        (
            {
                "project_variables": ["version", "contact", "title"],
                "mandatory_adoptable_fields": ["version", "contact", "title"],
            },
            ["contact", "title"],
            "Project fields 'contact' and 'title' were not set.",
        ),
    ],
    indirect=["app_metadata", "fake_project_dict"],
)
def test_update_project_variable_unset(
    app_metadata, fake_project, fake_project_dict, fake_services, result
):
    """Test project variables that must be set after the lifecycle runs."""
    service = FakePackageService(
        app_metadata,
        fake_services,
    )

    service._services.lifecycle.project_info.set_project_var(
        "version", "foo", raw_write=True
    )

    with pytest.raises(errors.PartsLifecycleError) as exc_info:
        service.update_project()

    assert str(exc_info.value) == result


@pytest.mark.parametrize(
    ("app_metadata", "fake_project_dict"),
    [
        (
            {
                "project_variables": ["version", "contact"],
                "mandatory_adoptable_fields": ["version"],
            },
            ["contact"],
        ),
        (
            {
                "project_variables": ["version", "contact", "title"],
                "mandatory_adoptable_fields": ["version"],
            },
            ["contact", "title"],
        ),
    ],
    indirect=["app_metadata", "fake_project_dict"],
)
def test_update_project_variable_optional(
    app_metadata,
    fake_project_dict,
    fake_project,
    fake_services,
):
    """Test project variables that can be optionally set."""
    service = FakePackageService(
        app_metadata,
        fake_services,
    )

    service._services.lifecycle.project_info.set_project_var(
        "version", "foo", raw_write=True
    )

    service.update_project()

    assert fake_services.get("project").get().version == "foo"
