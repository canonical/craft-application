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

import os
import pathlib
import shutil
import subprocess
from dataclasses import dataclass
from importlib import metadata
from typing import TYPE_CHECKING, Any
from unittest.mock import Mock

import craft_parts
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

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator


def _create_fake_build_plan(num_infos: int = 1) -> list[models.BuildInfo]:
    """Create a build plan that is able to execute on the running system."""
    arch = util.get_host_architecture()
    base = util.get_host_base()
    return [models.BuildInfo("foo", arch, arch, base)] * num_infos


@pytest.fixture(autouse=True)
def reset_services():
    yield
    service_factory.ServiceFactory.reset()


@pytest.fixture
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
def app_metadata(features, fake_config_model) -> craft_application.AppMetadata:
    with pytest.MonkeyPatch.context() as m:
        m.setattr(metadata, "version", lambda _: "3.14159")
        return craft_application.AppMetadata(
            "testcraft",
            "A fake app for testing craft-application",
            source_ignore_patterns=["*.snap", "*.charm", "*.starcraft"],
            features=craft_application.AppFeatures(**features),
            docs_url="www.testcraft.example/docs/{version}",
            ConfigModel=fake_config_model,
        )


@pytest.fixture
def app_metadata_docs(features) -> craft_application.AppMetadata:
    with pytest.MonkeyPatch.context() as m:
        m.setattr(metadata, "version", lambda _: "3.14159")
        return craft_application.AppMetadata(
            "testcraft",
            "A fake app for testing craft-application",
            docs_url="http://testcraft.example",
            source_ignore_patterns=["*.snap", "*.charm", "*.starcraft"],
            features=craft_application.AppFeatures(**features),
        )


@pytest.fixture
def fake_project() -> models.Project:
    arch = util.get_host_architecture()
    return models.Project(
        name="full-project",  # pyright: ignore[reportArgumentType]
        title="A fully-defined project",  # pyright: ignore[reportArgumentType]
        base="ubuntu@24.04",
        version="1.0.0.post64+git12345678",  # pyright: ignore[reportArgumentType]
        contact="author@project.org",
        issues="https://github.com/canonical/craft-application/issues",
        source_code="https://github.com/canonical/craft-application",  # pyright: ignore[reportArgumentType]
        summary="A fully-defined craft-application project.",  # pyright: ignore[reportArgumentType]
        description="A fully-defined craft-application project. (description)",
        license="LGPLv3",
        parts={"my-part": {"plugin": "nil"}},
        platforms={"foo": models.Platform(build_on=[arch], build_for=[arch])},
        package_repositories=None,
        adopt_info=None,
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
            project: models.Project,
            services: services.ServiceFactory,
            **kwargs: Any,
        ):
            kwargs.pop("build_plan", None)  # We'll use ours
            super().__init__(
                app,
                services,
                project=project,
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
    fake_init_service_class,
    fake_remote_build_service_class,
):
    services.ServiceFactory.register("package", fake_package_service_class)
    services.ServiceFactory.register("lifecycle", fake_lifecycle_service_class)
    services.ServiceFactory.register("init", fake_init_service_class)
    services.ServiceFactory.register("remote_build", fake_remote_build_service_class)
    factory = services.ServiceFactory(app_metadata, project=fake_project)
    factory.update_kwargs(
        "lifecycle", work_dir=tmp_path, cache_dir=tmp_path / "cache", build_plan=[]
    )
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
def app(app_metadata, fake_services):
    return FakeApplication(app_metadata, fake_services)


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
