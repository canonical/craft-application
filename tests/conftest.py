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

import pathlib
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


class MyProject(craft_application.models.Project):
    def get_build_plan(self) -> List[models.BuildInfo]:
        arch = craft_application.util.get_host_architecture()
        return [models.BuildInfo(arch, arch, bases.BaseName("ubuntu", "22.04"))]


@pytest.fixture()
def app_metadata() -> craft_application.AppMetadata:
    with pytest.MonkeyPatch.context() as m:
        m.setattr(metadata, "version", lambda _: "3.14159")
        return craft_application.AppMetadata(
            "testcraft",
            "A fake app for testing craft-application",
            ProjectClass=MyProject,
            source_ignore_patterns=["*.snap", "*.charm", "*.starcraft"],
        )


@pytest.fixture()
def fake_project() -> MyProject:
    return MyProject(
        name="full-project",  # pyright: ignore[reportGeneralTypeIssues]
        title="A fully-defined project",  # pyright: ignore[reportGeneralTypeIssues]
        base="core24",
        version="1.0.0.post64+git12345678",  # pyright: ignore[reportGeneralTypeIssues]
        contact="author@project.org",
        issues="https://github.com/canonical/craft-application/issues",
        source_code="https://github.com/canonical/craft-application",  # pyright: ignore[reportGeneralTypeIssues]
        summary="A fully-defined craft-application project.",  # pyright: ignore[reportGeneralTypeIssues]
        description="A fully-defined craft-application project. (description)",
        license="LGPLv3",
        parts={"my-part": {"plugin": "nil"}},
    )


@pytest.fixture()
def enable_overlay() -> Iterator[craft_parts.Features]:
    """Enable the overlay feature in craft_parts for the relevant test."""
    craft_parts.Features.reset()
    yield craft_parts.Features(enable_overlay=True)
    craft_parts.Features.reset()


@pytest.fixture()
def lifecycle_service(
    app_metadata, fake_project, tmp_path
) -> services.LifecycleService:
    work_dir = tmp_path / "work"
    cache_dir = tmp_path / "cache"
    build_for = util.get_host_architecture()

    return services.LifecycleService(
        app_metadata,
        fake_project,
        work_dir=work_dir,
        cache_dir=cache_dir,
        build_for=build_for,
    )


@pytest.fixture(params=list(EmitterMode))
def emitter_verbosity(request):
    reset_verbosity = emit.get_mode()
    emit.set_mode(request.param)
    yield request.param
    emit.set_mode(reset_verbosity)


@pytest.fixture()
def fake_package_service_class():
    class FakePackageService(services.PackageService):
        def pack(
            self, prime_dir: pathlib.Path, dest: pathlib.Path
        ) -> list[pathlib.Path]:
            assert prime_dir.exists()
            pkg = dest / "package.tar.zst"
            pkg.touch()
            return [pkg]

        @property
        def metadata(self) -> models.BaseMetadata:
            return models.BaseMetadata()

    return FakePackageService


@pytest.fixture()
def fake_lifecycle_service_class(tmp_path):
    class FakeLifecycleService(services.LifecycleService):
        def __init__(
            self,
            app: application.AppMetadata,
            project: models.Project,
            **lifecycle_kwargs: Any,
        ):
            super().__init__(
                app,
                project,
                work_dir=tmp_path / "work",
                cache_dir=tmp_path / "cache",
                build_for=util.get_host_architecture(),
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
