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


class ST160PackageService(FakePackageService):
    def get_artifacts(self) -> dict[str | None, pathlib.Path]:
        return {None: pathlib.Path("artifact")}

    def _pack(self, *, name: str | None = None, path: Path) -> None:
        return None


class MultiArtifactPackageService(FakePackageService):
    def __init__(self, app_metadata, fake_services, *, artifacts: dict[str | None, Path]):
        super().__init__(app_metadata, fake_services)
        self._artifacts = artifacts
        self.packed: list[tuple[str | None, Path]] = []

    def get_artifacts(self) -> dict[str | None, pathlib.Path]:
        return self._artifacts

    def _pack(self, *, name: str | None = None, path: Path) -> None:
        self.packed.append((name, path))


class DecoratedPackageService(FakePackageService):
    @package.package_file("metadata.yaml")
    def _metadata(self, partition: str | None = None) -> str:
        return "metadata"

    @package.package_file("meta/default.yaml", partition_re="default")
    def _default_only(self, partition: str | None = None) -> str:
        return f"default:{partition}"

    @package.package_file("meta/other.yaml", partition_re="other")
    def _other_only(self, partition: str | None = None) -> str:
        return f"other:{partition}"


class InheritedDecoratedPackageService(DecoratedPackageService):
    @package.package_file("meta/inherited.yaml", partition_re="default")
    def _inherited_only(self, partition: str | None = None) -> str:
        return f"inherited:{partition}"


class OverriddenDecoratedPackageService(DecoratedPackageService):
    @package.package_file("meta/replaced.yaml", partition_re="default")
    def _default_only(self, partition: str | None = None) -> str:
        return f"replaced:{partition}"


def test_write_metadata(tmp_path, app_metadata, fake_project, fake_services):
    service = FakePackageService(app_metadata, fake_services)
    metadata_file = tmp_path / "metadata.yaml"
    assert not metadata_file.exists()

    service.write_metadata(tmp_path)

    assert metadata_file.is_file()
    metadata = models.BaseMetadata.from_yaml_file(metadata_file)
    assert metadata == service.metadata


def test_package_service_supports_conditional_repack_false(
    app_metadata, fake_project, fake_services
):
    service = FakePackageService(app_metadata, fake_services)

    assert service.supports_conditional_repack is False


def test_package_service_supports_conditional_repack_true(
    app_metadata, fake_project, fake_services
):
    service = ST160PackageService(app_metadata, fake_services)

    assert service.supports_conditional_repack is True


def test_needs_packing_true_when_lifecycle_requires_repack(
    app_metadata, fake_project, fake_services, mocker
):
    service = ST160PackageService(app_metadata, fake_services)
    mocker.patch.object(type(service._services.lifecycle), "requires_repack", new=True)

    assert service.needs_packing(None) is True


@pytest.mark.parametrize(
    "app_metadata",
    [{"always_repack": True}],
    indirect=True,
)
def test_needs_packing_true_when_always_repack_enabled(
    app_metadata, fake_project, fake_services, mocker, tmp_path
):
    artifact_path = tmp_path / "artifact"
    artifact_path.touch()
    service = MultiArtifactPackageService(
        app_metadata, fake_services, artifacts={None: artifact_path}
    )
    mocker.patch.object(type(service._services.lifecycle), "requires_repack", new=False)

    assert service.needs_packing(None) is True


def test_needs_packing_true_when_artifact_missing(
    app_metadata, fake_project, fake_services, mocker
):
    service = ST160PackageService(app_metadata, fake_services)
    mocker.patch.object(type(service._services.lifecycle), "requires_repack", new=False)

    assert service.needs_packing(None) is True


def test_needs_packing_false_when_artifact_exists(
    app_metadata, fake_project, fake_services, mocker, tmp_path
):
    artifact_path = tmp_path / "artifact"
    artifact_path.touch()
    service = MultiArtifactPackageService(
        app_metadata, fake_services, artifacts={None: artifact_path}
    )
    mocker.patch.object(type(service._services.lifecycle), "requires_repack", new=False)

    assert service.needs_packing(None) is False


def test_pack_artifacts_only_packs_needed_artifacts(
    app_metadata, fake_project, fake_services, mocker, tmp_path
):
    artifacts = {
        None: tmp_path / "main.tar.zst",
        "tools": tmp_path / "tools.tar.zst",
    }
    artifacts["tools"].touch()
    service = MultiArtifactPackageService(app_metadata, fake_services, artifacts=artifacts)
    mocker.patch.object(type(service._services.lifecycle), "requires_repack", new=False)

    result = service.pack_artifacts()

    assert result == {None: True, "tools": False}
    assert service.packed == [(None, artifacts[None])]


def test_package_files_without_partition_filter(
    app_metadata, fake_project, fake_services
):
    service = DecoratedPackageService(app_metadata, fake_services)

    assert service._package_files() == [
        package.PackageFileEntry(
            relative_path=pathlib.PurePosixPath("metadata.yaml"),
            method_name="_metadata",
            partition_re=None,
        ),
        package.PackageFileEntry(
            relative_path=pathlib.PurePosixPath("meta/default.yaml"),
            method_name="_default_only",
            partition_re="default",
        )
    ]


def test_package_files_filtered_for_partition(
    app_metadata, fake_project, fake_services
):
    service = DecoratedPackageService(app_metadata, fake_services)

    assert service._package_files("default") == [
        package.PackageFileEntry(
            relative_path=pathlib.PurePosixPath("metadata.yaml"),
            method_name="_metadata",
            partition_re=None,
        ),
        package.PackageFileEntry(
            relative_path=pathlib.PurePosixPath("meta/default.yaml"),
            method_name="_default_only",
            partition_re="default",
        ),
    ]


def test_package_files_match_default_partition_for_unnamed_artifact(
    app_metadata, fake_project, fake_services
):
    service = DecoratedPackageService(app_metadata, fake_services)

    assert service._package_files(None) == [
        package.PackageFileEntry(
            relative_path=pathlib.PurePosixPath("metadata.yaml"),
            method_name="_metadata",
            partition_re=None,
        ),
        package.PackageFileEntry(
            relative_path=pathlib.PurePosixPath("meta/default.yaml"),
            method_name="_default_only",
            partition_re="default",
        ),
    ]


def test_package_files_filtered_for_different_partition(
    app_metadata, fake_project, fake_services
):
    service = DecoratedPackageService(app_metadata, fake_services)

    assert service._package_files("other") == [
        package.PackageFileEntry(
            relative_path=pathlib.PurePosixPath("metadata.yaml"),
            method_name="_metadata",
            partition_re=None,
        ),
        package.PackageFileEntry(
            relative_path=pathlib.PurePosixPath("meta/other.yaml"),
            method_name="_other_only",
            partition_re="other",
        ),
    ]


def test_package_files_include_inherited_entries(
    app_metadata, fake_project, fake_services
):
    service = InheritedDecoratedPackageService(app_metadata, fake_services)

    assert service._package_files("default") == [
        package.PackageFileEntry(
            relative_path=pathlib.PurePosixPath("metadata.yaml"),
            method_name="_metadata",
            partition_re=None,
        ),
        package.PackageFileEntry(
            relative_path=pathlib.PurePosixPath("meta/default.yaml"),
            method_name="_default_only",
            partition_re="default",
        ),
        package.PackageFileEntry(
            relative_path=pathlib.PurePosixPath("meta/inherited.yaml"),
            method_name="_inherited_only",
            partition_re="default",
        ),
    ]


def test_package_files_override_base_registration(
    app_metadata, fake_project, fake_services
):
    service = OverriddenDecoratedPackageService(app_metadata, fake_services)

    assert service._package_files("default") == [
        package.PackageFileEntry(
            relative_path=pathlib.PurePosixPath("metadata.yaml"),
            method_name="_metadata",
            partition_re=None,
        ),
        package.PackageFileEntry(
            relative_path=pathlib.PurePosixPath("meta/replaced.yaml"),
            method_name="_default_only",
            partition_re="default",
        ),
    ]


def test_pack_state_compatibility_views_from_canonical_shape():
    state = models.PackState(
        artifacts=[
            models.PackedArtifact(name=None, path=pathlib.Path("package.tar.zst")),
            models.PackedArtifact(
                name="tools", path=pathlib.Path("tools.tar.zst")
            ),
        ]
    )

    assert state.artifact == pathlib.Path("package.tar.zst")
    assert state.resources == {"tools": pathlib.Path("tools.tar.zst")}


def test_pack_state_named_default_artifact_does_not_collide():
    state = models.PackState(
        artifacts=[
            models.PackedArtifact(name=None, path=pathlib.Path("main.tar.zst")),
            models.PackedArtifact(name="default", path=pathlib.Path("default.tar.zst")),
        ]
    )

    assert state.artifact == pathlib.Path("main.tar.zst")
    assert state.resources == {"default": pathlib.Path("default.tar.zst")}


def test_read_state_accepts_legacy_artifact_and_resources(
    app_metadata, fake_project, fake_services, fake_platform, mocker
):
    service = FakePackageService(app_metadata, fake_services)
    fake_services.get("build_plan").set_platforms(fake_platform)
    mocker.patch.object(
        fake_services.get("build_plan"),
        "plan",
        return_value=fake_services.get("build_plan").create_build_plan(
            platforms=fake_platform,
            build_for=None,
            build_on=None,
        )[:1],
    )
    state_service = fake_services.get("state")
    platform = service._build_info.platform

    state_service.set("artifact", platform, value="package.tar.zst")
    state_service.set(
        "resources",
        platform,
        value={"tools": "tools.tar.zst"},
    )

    state = service.read_state()

    assert state.artifact == pathlib.Path("package.tar.zst")
    assert state.resources == {"tools": pathlib.Path("tools.tar.zst")}


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
