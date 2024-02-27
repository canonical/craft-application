# This file is part of craft_application.
#
# Copyright 2023 Canonical Ltd.
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
"""Shared data for all craft-application tests."""
from __future__ import annotations

import os
import pathlib
import shutil
from importlib import metadata
from typing import TYPE_CHECKING, Any

import craft_application
import craft_parts
import pytest
from craft_application import application, models, services, util
from craft_cli import EmitterMode, emit
from craft_providers import bases

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator


class Platform(models.CraftBaseModel):
    """Platform definition."""

    build_on: str
    build_for: str


def _create_fake_build_plan(num_infos: int = 1) -> list[models.BuildInfo]:
    """Create a build plan that is able to execute on the running system."""
    arch = util.get_host_architecture()
    base = util.get_host_base()
    return [models.BuildInfo("foo", arch, arch, base)] * num_infos


class MyBuildPlanner(models.BuildPlanner):
    """Build planner definition for tests."""

    def get_build_plan(self) -> list[models.BuildInfo]:
        return _create_fake_build_plan()


@pytest.fixture()
def features(request) -> dict[str, bool]:
    """Fixture that controls the enabled features.

    To use it, mark the test with the features that should be enabled. For example:

    @pytest.mark.enable_features("build_secrets")
    def test_with_build_secrets(...)
    """
    features = {}

    for feature_marker in request.node.iter_markers("enable_features"):
        for feature_name in feature_marker.args:
            features[feature_name] = True

    return features


@pytest.fixture()
def app_metadata(features) -> craft_application.AppMetadata:
    with pytest.MonkeyPatch.context() as m:
        m.setattr(metadata, "version", lambda _: "3.14159")
        return craft_application.AppMetadata(
            "testcraft",
            "A fake app for testing craft-application",
            BuildPlannerClass=MyBuildPlanner,
            source_ignore_patterns=["*.snap", "*.charm", "*.starcraft"],
            features=craft_application.AppFeatures(**features),
        )


@pytest.fixture()
def fake_project() -> models.Project:
    arch = util.get_host_architecture()
    return models.Project(
        name="full-project",  # pyright: ignore[reportArgumentType]
        title="A fully-defined project",  # pyright: ignore[reportArgumentType]
        base="core24",
        version="1.0.0.post64+git12345678",  # pyright: ignore[reportArgumentType]
        contact="author@project.org",
        issues="https://github.com/canonical/craft-application/issues",
        source_code="https://github.com/canonical/craft-application",  # pyright: ignore[reportArgumentType]
        summary="A fully-defined craft-application project.",  # pyright: ignore[reportArgumentType]
        description="A fully-defined craft-application project. (description)",
        license="LGPLv3",
        parts={"my-part": {"plugin": "nil"}},
        platforms={"foo": Platform(build_on=arch, build_for=arch)},
        package_repositories=None,
        adopt_info=None,
    )


@pytest.fixture()
def fake_build_plan(request) -> list[models.BuildInfo]:
    num_infos = getattr(request, "param", 1)
    return _create_fake_build_plan(num_infos)


@pytest.fixture()
def full_build_plan(mocker) -> list[models.BuildInfo]:
    """A big build plan with multiple bases and build-for targets."""
    host_arch = util.get_host_architecture()
    build_plan = []
    for release in ("20.04", "22.04", "24.04"):
        for build_for in (host_arch, "s390x", "riscv64"):
            build_plan.append(
                models.BuildInfo(
                    f"ubuntu-{release}-{build_for}",
                    host_arch,
                    build_for,
                    bases.BaseName("ubuntu", release),
                )
            )

    mocker.patch.object(MyBuildPlanner, "get_build_plan", return_value=build_plan)
    return build_plan


@pytest.fixture()
def enable_overlay() -> Iterator[craft_parts.Features]:
    """Enable the overlay feature in craft_parts for the relevant test."""
    if not os.getenv("CI") and not shutil.which("fuse-overlayfs"):
        pytest.skip("fuse-overlayfs not installed, skipping overlay tests.")
    craft_parts.Features.reset()
    yield craft_parts.Features(enable_overlay=True)
    craft_parts.Features.reset()


@pytest.fixture()
def lifecycle_service(
    app_metadata, fake_project, fake_services, fake_build_plan, mocker, tmp_path
) -> services.LifecycleService:
    work_dir = tmp_path / "work"
    cache_dir = tmp_path / "cache"

    service = services.LifecycleService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=work_dir,
        cache_dir=cache_dir,
        platform=None,
        build_plan=fake_build_plan,
    )
    service.setup()
    mocker.patch.object(
        service._lcm,
        "get_pull_assets",
        new=lambda **p: {"foo": "bar"} if p["part_name"] == "my-part" else {},
    )
    mocker.patch.object(
        service._lcm,
        "get_primed_stage_packages",
        new=lambda **p: ["pkg1", "pkg2"] if p["part_name"] == "my-part" else {},
    )
    return service


@pytest.fixture()
def request_service(app_metadata, fake_services) -> services.RequestService:
    """A working version of the requests service."""
    return services.RequestService(app=app_metadata, services=fake_services)


@pytest.fixture(params=list(EmitterMode))
def emitter_verbosity(request):
    reset_verbosity = emit.get_mode()
    emit.set_mode(request.param)
    yield request.param
    emit.set_mode(reset_verbosity)


@pytest.fixture()
def fake_provider_service_class(fake_build_plan):
    class FakeProviderService(services.ProviderService):
        def __init__(
            self,
            app: application.AppMetadata,
            services: services.ServiceFactory,
            *,
            project: models.Project,
        ):
            super().__init__(
                app,
                services,
                project=project,
                work_dir=pathlib.Path(),
                build_plan=fake_build_plan,
            )

    return FakeProviderService


@pytest.fixture()
def fake_package_service_class():
    class FakePackageService(services.PackageService):
        def pack(
            self, prime_dir: pathlib.Path, dest: pathlib.Path
        ) -> list[pathlib.Path]:
            assert prime_dir.exists()
            pkg = dest / f"package_{self._project.version}.tar.zst"
            pkg.touch()
            return [pkg]

        @property
        def metadata(self) -> models.BaseMetadata:
            return models.BaseMetadata()

    return FakePackageService


@pytest.fixture()
def fake_lifecycle_service_class(tmp_path, fake_build_plan):
    class FakeLifecycleService(services.LifecycleService):
        def __init__(
            self,
            app: application.AppMetadata,
            project: models.Project,
            services: services.ServiceFactory,
            **lifecycle_kwargs: Any,
        ):
            super().__init__(
                app,
                services,
                project=project,
                work_dir=tmp_path / "work",
                cache_dir=tmp_path / "cache",
                platform=None,
                build_plan=fake_build_plan,
                **lifecycle_kwargs,
            )

    return FakeLifecycleService


@pytest.fixture()
def fake_services(
    app_metadata, fake_project, fake_lifecycle_service_class, fake_package_service_class
):
    return services.ServiceFactory(
        app_metadata,
        project=fake_project,
        PackageClass=fake_package_service_class,
        LifecycleClass=fake_lifecycle_service_class,
    )
