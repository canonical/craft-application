# This file is part of craft_application.
#
# Copyright 2023-2024 Canonical Ltd.
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

import functools
import io
import os
import pathlib
import shutil
import subprocess
from dataclasses import dataclass
from importlib import metadata
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import craft_parts
import craft_platforms
import distro
import jinja2
import pydantic
import pytest
from craft_cli import EmitterMode, emit
from craft_providers import bases
from jinja2 import FileSystemLoader
from typing_extensions import override

import craft_application
from craft_application import application, git, launchpad, models, services, util
from craft_application.services import service_factory
from craft_application.util import yaml

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator


FAKE_PROJECT_YAML_TEMPLATE = """\
name: full-project
title: A fully-defined project
summary: A fully-defined craft-application project.
description: |
  A fully-defined craft-application project.

  This is a full description.
version: 1.0.0.post64+git12345678
license: LGPLv3

base: {base}
platforms:
  64-bit-pc:
    build-on: [amd64]
    build-for: [amd64]
  some-phone:
    build-on: [amd64, arm64, s390x]
    build-for: [arm64]
  ppc64el:
  risky:
    build-on: [amd64, arm64, ppc64el, riscv64, s390x]
    build-for: [riscv64]
  s390x:
    build-on: [amd64, arm64, ppc64el, riscv64, s390x]
    build-for: [s390x]
  platform-independent:
    build-on: [amd64, arm64, ppc64el, riscv64, s390x]
    build-for: [all]

contact: author@project.org
issues: https://github.com/canonical/craft-application/issues
source-code: https://github.com/canonical/craft-application

parts:
  some-part:
    plugin: nil
    build-environment:
      - BUILD_ON: $CRAFT_ARCH_BUILD_ON
      - BUILD_FOR: $CRAFT_ARCH_BUILD_FOR
"""


@pytest.fixture(
    params=[
        "64-bit-pc",
        "some-phone",
        "ppc64el",
        "risky",
        "s390x",
        "platform-independent",
    ]
)
def fake_platform(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def fake_project_yaml():
    current_base = craft_platforms.DistroBase.from_linux_distribution(
        distro.LinuxDistribution(
            include_lsb=False, include_uname=False, include_oslevel=False
        )
    )
    return FAKE_PROJECT_YAML_TEMPLATE.format(
        base=f"{current_base.distribution}@{current_base.series}"
    )


@pytest.fixture
def fake_project_file(in_project_path, fake_project_yaml):
    project_file = in_project_path / "testcraft.yaml"
    project_file.write_text(fake_project_yaml)

    return project_file


@pytest.fixture
def fake_project(fake_project_yaml) -> models.Project:
    with io.StringIO(fake_project_yaml) as project_io:
        return models.Project.unmarshal(yaml.safe_yaml_load(project_io))


def _create_fake_build_plan(num_infos: int = 1) -> list[models.BuildInfo]:
    """Create a build plan that is able to execute on the running system."""
    arch = util.get_host_architecture()
    base = util.get_host_base()
    return [models.BuildInfo("foo", arch, arch, base)] * num_infos


@pytest.fixture(autouse=True)
def reset_services():
    yield
    service_factory.ServiceFactory.reset()


class FakeConfigModel(craft_application.ConfigModel):
    my_str: str
    my_int: int
    my_bool: bool
    my_default_str: str = "default"
    my_default_int: int = -1
    my_default_bool: bool = True
    my_default_factory: dict[str, str] = pydantic.Field(
        default_factory=lambda: {"dict": "yes"}
    )
    my_arch: launchpad.Architecture


@pytest.fixture(scope="session")
def fake_config_model() -> type[FakeConfigModel]:
    return FakeConfigModel


@pytest.fixture(scope="session")
def default_app_metadata(fake_config_model) -> craft_application.AppMetadata:
    with pytest.MonkeyPatch.context() as m:
        m.setattr(metadata, "version", lambda _: "3.14159")
        return craft_application.AppMetadata(
            "testcraft",
            "A fake app for testing craft-application",
            source_ignore_patterns=["*.snap", "*.charm", "*.starcraft"],
            ConfigModel=fake_config_model,
        )


@pytest.fixture
def app_metadata(fake_config_model) -> craft_application.AppMetadata:
    with pytest.MonkeyPatch.context() as m:
        m.setattr(metadata, "version", lambda _: "3.14159")
        return craft_application.AppMetadata(
            "testcraft",
            "A fake app for testing craft-application",
            source_ignore_patterns=["*.snap", "*.charm", "*.starcraft"],
            docs_url="www.testcraft.example/docs/{version}",
            ConfigModel=fake_config_model,
        )


@pytest.fixture
def app_metadata_docs() -> craft_application.AppMetadata:
    with pytest.MonkeyPatch.context() as m:
        m.setattr(metadata, "version", lambda _: "3.14159")
        return craft_application.AppMetadata(
            "testcraft",
            "A fake app for testing craft-application",
            docs_url="http://testcraft.example",
            source_ignore_patterns=["*.snap", "*.charm", "*.starcraft"],
        )


@pytest.fixture
def fake_build_plan(request) -> list[models.BuildInfo]:
    num_infos = getattr(request, "param", 1)
    return _create_fake_build_plan(num_infos)


@pytest.fixture
def full_build_plan(mocker) -> list[models.BuildInfo]:
    """A big build plan with multiple bases and build-for targets."""
    host_arch = util.get_host_architecture()
    build_plan = []
    for release in ("20.04", "22.04", "24.04"):
        build_plan.extend(
            models.BuildInfo(
                f"ubuntu-{release}-{build_for}",
                host_arch,
                build_for,
                bases.BaseName("ubuntu", release),
            )
            for build_for in (host_arch, "s390x", "riscv64")
        )

    mocker.patch.object(models.BuildPlanner, "get_build_plan", return_value=build_plan)
    return build_plan


@pytest.fixture
def enable_partitions() -> Iterator[craft_parts.Features]:
    """Enable the partitions feature in craft_parts for the relevant test."""
    enable_overlay = craft_parts.Features().enable_overlay

    craft_parts.Features.reset()
    yield craft_parts.Features(enable_overlay=enable_overlay, enable_partitions=True)
    craft_parts.Features.reset()


@pytest.fixture
def enable_overlay() -> Iterator[craft_parts.Features]:
    """Enable the overlay feature in craft_parts for the relevant test."""
    if not os.getenv("CI") and not shutil.which("fuse-overlayfs"):
        pytest.skip("fuse-overlayfs not installed, skipping overlay tests.")

    enable_partitions = craft_parts.Features().enable_partitions
    craft_parts.Features.reset()
    yield craft_parts.Features(enable_overlay=True, enable_partitions=enable_partitions)
    craft_parts.Features.reset()


@pytest.fixture
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


@pytest.fixture
def request_service(app_metadata, fake_services) -> services.RequestService:
    """A working version of the requests service."""
    return services.RequestService(app=app_metadata, services=fake_services)


@pytest.fixture(params=list(EmitterMode))
def emitter_verbosity(request):
    reset_verbosity = emit.get_mode()
    emit.set_mode(request.param)
    yield request.param
    emit.set_mode(reset_verbosity)


@pytest.fixture
def fake_project_service_class(fake_project) -> type[services.ProjectService]:
    class FakeProjectService(services.ProjectService):
        @override
        def _load_raw_project(self):
            return fake_project.marshal()

        # Don't care if the project file exists during this testing.
        # Silencing B019 because we're replicating an inherited method.
        @override
        @functools.lru_cache(maxsize=1)  # noqa: B019
        def resolve_project_file_path(self):
            return (self._project_dir / f"{self._app.name}.yaml").resolve()

        def set(self, value: models.Project) -> None:
            """Set the project model. Only for use during testing!"""
            self._project_model = value

    return FakeProjectService


@pytest.fixture
def fake_provider_service_class(fake_build_plan, project_path):
    class FakeProviderService(services.ProviderService):
        def __init__(
            self,
            app: application.AppMetadata,
            services: services.ServiceFactory,
        ):
            super().__init__(
                app,
                services,
                work_dir=project_path,
                build_plan=fake_build_plan,
            )

    return FakeProviderService


@pytest.fixture
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


@pytest.fixture
def fake_lifecycle_service_class(tmp_path, fake_build_plan):
    class FakeLifecycleService(services.LifecycleService):
        def __init__(
            self,
            app: application.AppMetadata,
            services: services.ServiceFactory,
            **kwargs: Any,
        ):
            kwargs.pop("build_plan", None)  # We'll use ours
            super().__init__(
                app,
                services,
                work_dir=kwargs.pop("work_dir", tmp_path / "work"),
                cache_dir=kwargs.pop("cache_dir", tmp_path / "cache"),
                platform=None,
                build_plan=fake_build_plan,
                **kwargs,
            )

    return FakeLifecycleService


@pytest.fixture
def fake_init_service_class(tmp_path):
    class FakeInitService(services.InitService):
        def _get_loader(self, template_dir: pathlib.Path) -> jinja2.BaseLoader:
            return FileSystemLoader(tmp_path / "templates" / template_dir)

    return FakeInitService


@pytest.fixture
def fake_remote_build_service_class():
    class FakeRemoteBuild(services.RemoteBuildService):
        @override
        def _get_lp_client(self) -> launchpad.Launchpad:
            return Mock(spec=launchpad.Launchpad)

    return FakeRemoteBuild


@pytest.fixture
def fake_services(
    tmp_path,
    app_metadata,
    fake_project,
    fake_lifecycle_service_class,
    fake_package_service_class,
    fake_project_service_class,
    fake_init_service_class,
    fake_remote_build_service_class,
    project_path,
):
    services.ServiceFactory.register("package", fake_package_service_class)
    services.ServiceFactory.register("lifecycle", fake_lifecycle_service_class)
    services.ServiceFactory.register("init", fake_init_service_class)
    services.ServiceFactory.register("remote_build", fake_remote_build_service_class)
    services.ServiceFactory.register("project", fake_project_service_class)
    factory = services.ServiceFactory(app_metadata)
    factory.update_kwargs(
        "lifecycle", work_dir=tmp_path, cache_dir=tmp_path / "cache", build_plan=[]
    )
    factory.update_kwargs(
        "project",
        project_dir=project_path,
    )
    factory.get("project").render_once()
    return factory


class FakeApplication(application.Application):
    """An application class explicitly for testing. Adds some convenient test hooks."""

    platform: str = "unknown-platform"
    build_on: str = "unknown-build-on"
    build_for: str | None = "unknown-build-for"

    def set_project(self, project):
        self._Application__project = project

    @override
    def _extra_yaml_transform(
        self,
        yaml_data: dict[str, Any],
        *,
        build_on: str,
        build_for: str | None,
    ) -> dict[str, Any]:
        self.build_on = build_on
        self.build_for = build_for

        return yaml_data


@pytest.fixture
def app(app_metadata, fake_services, tmp_path):
    application = FakeApplication(app_metadata, fake_services)
    application._work_dir = tmp_path
    return application


@pytest.fixture
def manifest_data_dir():
    return pathlib.Path(__file__).parent / "data/manifest"


@pytest.fixture
def new_dir(tmp_path):
    """Change to a new temporary directory."""
    cwd = pathlib.Path.cwd()
    os.chdir(tmp_path)

    yield tmp_path

    os.chdir(cwd)


@pytest.fixture
def empty_working_directory(
    tmp_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
) -> pathlib.Path:
    repo_dir = pathlib.Path(tmp_path, "test-repo")
    repo_dir.mkdir()
    monkeypatch.chdir(repo_dir)
    return repo_dir


@pytest.fixture
def empty_repository(empty_working_directory: pathlib.Path) -> pathlib.Path:
    subprocess.run(["git", "init"], check=True)
    return empty_working_directory


@dataclass
class RepositoryDefinition:
    repository_path: pathlib.Path
    commit: str
    tag: str | None = None

    @property
    def short_commit(self) -> str:
        """Return abbreviated commit."""
        return git.short_commit_sha(self.commit)


@pytest.fixture
def repository_with_commit(empty_repository: pathlib.Path) -> RepositoryDefinition:
    repo = git.GitRepo(empty_repository)
    (empty_repository / "Some file").touch()
    repo.add_all()
    commit_sha = repo.commit("1")
    return RepositoryDefinition(
        repository_path=empty_repository,
        commit=commit_sha,
    )


@pytest.fixture
def repository_with_annotated_tag(
    repository_with_commit: RepositoryDefinition,
) -> RepositoryDefinition:
    test_tag = "v3.2.1"
    subprocess.run(
        ["git", "config", "--local", "user.name", "Testcraft", test_tag], check=True
    )
    subprocess.run(
        ["git", "config", "--local", "user.email", "testcraft@canonical.com", test_tag],
        check=True,
    )
    subprocess.run(["git", "tag", "-a", "-m", "testcraft tag", test_tag], check=True)
    repository_with_commit.tag = test_tag
    return repository_with_commit


@pytest.fixture
def repository_with_unannotated_tag(
    repository_with_commit: RepositoryDefinition,
) -> RepositoryDefinition:
    subprocess.run(["git", "config", "--local", "user.name", "Testcraft"], check=True)
    subprocess.run(
        ["git", "config", "--local", "user.email", "testcraft@canonical.com"],
        check=True,
    )
    test_tag = "non-annotated"
    subprocess.run(["git", "tag", test_tag], check=True)
    repository_with_commit.tag = test_tag
    return repository_with_commit
