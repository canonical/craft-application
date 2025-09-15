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

import copy
import os
import pathlib
import shutil
import subprocess
from dataclasses import dataclass
from importlib import metadata
from typing import TYPE_CHECKING, Any, cast
from unittest.mock import Mock

import craft_application
import craft_parts
import craft_platforms
import distro
import jinja2
import pydantic
import pytest
from craft_application import application, errors, git, launchpad, models, services
from craft_application.services import service_factory
from craft_application.services.fetch import FetchService
from craft_application.services.project import ProjectService
from craft_application.util import yaml
from craft_cli import EmitterMode, emit
from jinja2 import FileSystemLoader
from typing_extensions import override

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
    build-on: amd64  # Testing vectorisation of build-on
    build-for: [amd64]
  some-phone:
    build-on: [amd64, arm64, s390x]
    build-for: arm64  # Testing vectorisation of build-for
  ppc64el:  # Testing expansion of architecture name.
  risky:
    build-on: [amd64, arm64, ppc64el, riscv64, s390x]
    build-for: [riscv64]
  s390x:  # Test with build-on only
    build-on: [amd64, arm64, armhf, i386, ppc64el, riscv64, s390x]

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
    ],
    scope="session",
)
def fake_platform(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture
def platform_independent_project(fake_project_file, fake_project_dict):
    """Turn the fake project into a platform-independent project.

    This is needed because `build-for: [all]` implies a single platform. So
    """
    old_platforms = fake_project_dict["platforms"]
    fake_project_dict["platforms"] = {
        "platform-independent": {
            "build-on": [str(arch) for arch in craft_platforms.DebianArchitecture],
            "build-for": ["all"],
        }
    }
    fake_project_file.write_text(yaml.dump_yaml(fake_project_dict))
    yield
    fake_project_dict["platforms"] = old_platforms


@pytest.fixture(scope="session")
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


@pytest.fixture(scope="module")
def fake_project_dict(fake_project_yaml: str):
    return yaml.safe_yaml_load(fake_project_yaml)


@pytest.fixture
def fake_project(fake_project_dict) -> models.Project:
    project = copy.deepcopy(fake_project_dict)
    ProjectService._preprocess_platforms(project["platforms"])
    return models.Project.unmarshal(project)


@pytest.fixture(
    params=[
        craft_platforms.DistroBase("ubuntu", "18.04"),
        craft_platforms.DistroBase("ubuntu", "20.04"),
        craft_platforms.DistroBase("ubuntu", "22.04"),
        craft_platforms.DistroBase("ubuntu", "24.04"),
        craft_platforms.DistroBase("ubuntu", "24.10"),
        craft_platforms.DistroBase("ubuntu", "devel"),
        craft_platforms.DistroBase("almalinux", "9"),
    ],
    scope="session",
)
def fake_base(request: pytest.FixtureRequest):
    return request.param


@pytest.fixture(autouse=True)
def reset_services():
    yield
    service_factory.ServiceFactory.reset()


@pytest.fixture
def in_project_dir(project_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Put us in the project directory made by project_path."""
    monkeypatch.chdir(project_path)


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
def app_metadata(request, fake_config_model) -> craft_application.AppMetadata:
    """Default app metadata.

    :param request: kwargs to override metadata
    """
    kwargs = {
        "source_ignore_patterns": ["*.snap", "*.charm", "*.starcraft"],
        "docs_url": "www.testcraft.example/docs/{version}",
        "ConfigModel": fake_config_model,
        "supports_multi_base": True,
        "always_repack": False,
        "check_supported_base": True,
        **getattr(request, "param", {}),
    }

    with pytest.MonkeyPatch.context() as m:
        m.setattr(metadata, "version", lambda _: "3.14159")
        return craft_application.AppMetadata(
            "testcraft",
            "A fake app for testing craft-application",
            **kwargs,
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
def build_plan_service(fake_services):
    return fake_services.get("build_plan")


@pytest.fixture
def state_service(fake_services):
    return fake_services.get("state")


@pytest.fixture
def lifecycle_service(
    app_metadata, fake_project, fake_services, mocker, tmp_path
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
def fake_project_service_class(fake_project_dict) -> type[services.ProjectService]:
    class FakeProjectService(services.ProjectService):
        # This is a final method, but we're overriding it here for convenience when
        # doing internal testing.
        @override
        def _load_raw_project(self):  # type: ignore[reportIncompatibleMethodOverride]
            return fake_project_dict

        # Don't care if the project file exists during this testing.
        # Silencing B019 because we're replicating an inherited method.
        @override
        def resolve_project_file_path(self):
            return (self._project_dir / f"{self._app.name}.yaml").resolve()

        def set(self, value: models.Project) -> None:
            """Set the project model. Only for use during testing!"""
            self._project_model = value
            self._platform = next(iter(value.platforms))
            self._build_for = value.platforms[self._platform].build_for[0]  # type: ignore[reportOptionalSubscript]
            self._project_vars = craft_parts.ProjectVarInfo.unmarshal(
                {"a": craft_parts.ProjectVar(value="foo").marshal()}
            )

        @override
        def get_partitions_for(
            self,
            *,
            platform: str,
            build_for: str,
            build_on: craft_platforms.DebianArchitecture,
        ) -> list[str] | None:
            """Make this flexible for whether we have partitions or not.

            If we have partitions, we get the default, one for the platform and
            one for build_for.
            """
            if craft_parts.Features().enable_partitions:
                return ["default", *{platform, build_for}]
            return None

        def get_partitions(self) -> list[str] | None:
            """Make this flexible for whether we have partitions or not."""
            if craft_parts.Features().enable_partitions:
                return ["default", "a"]
            return None

    return FakeProjectService


@pytest.fixture
def fake_provider_service_class(project_path):
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
            )

    return FakeProviderService


@pytest.fixture
def fake_package_service_class():
    class FakePackageService(services.PackageService):
        def pack(
            self, prime_dir: pathlib.Path, dest: pathlib.Path
        ) -> list[pathlib.Path]:
            assert prime_dir.exists()
            pkg = dest / "package_1.0.tar.zst"
            pkg.touch()
            return [pkg]

        @property
        def metadata(self) -> models.BaseMetadata:
            return models.BaseMetadata()

    return FakePackageService


@pytest.fixture
def fake_lifecycle_service_class(tmp_path):
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
    request: pytest.FixtureRequest,
    tmp_path,
    app_metadata,
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
    factory.update_kwargs("project", project_dir=project_path)
    factory.update_kwargs("provider", work_dir=project_path)
    platform = (
        request.getfixturevalue("fake_platform")
        if "fake_platform" in request.fixturenames
        else None
    )
    build_for = (
        request.getfixturevalue("build_for")
        if "build_for" in request.fixturenames
        else None
    )

    try:
        factory.get("project").configure(platform=platform, build_for=build_for)
    except errors.ProjectGenerationError as exc:
        pytest.skip(str(exc))
    yield factory

    if fetch := cast(FetchService | None, factory._services.get("fetch")):
        fetch.shutdown(force=True)


class FakeApplication(application.Application):
    """An application class explicitly for testing. Adds some convenient test hooks."""

    platform: str = "unknown-platform"
    build_on: str = "unknown-build-on"
    build_for: str | None = "unknown-build-for"

    def set_project(self, project):
        self._Application__project = project


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
