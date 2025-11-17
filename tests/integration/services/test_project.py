# Copyright 2025 Canonical Ltd.
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
"""Integration tests for the ProjectService."""

import pathlib
import shutil

import craft_platforms
import pytest
from craft_application.services.project import ProjectService
from craft_application.util import yaml

PROJECT_FILES_PATH = pathlib.Path(__file__).parent / "project_files"


@pytest.fixture
def service(app_metadata, fake_services, in_project_path: pathlib.Path):
    return ProjectService(
        app=app_metadata, services=fake_services, project_dir=in_project_path
    )


@pytest.fixture(
    params=[
        pytest.param(path, id=path.name)
        for path in PROJECT_FILES_PATH.glob("testcraft-*.yaml")
    ]
)
def project_file(
    project_path: pathlib.Path, app_metadata, request: pytest.FixtureRequest
):
    project_file = project_path / f"{app_metadata.name}.yaml"
    shutil.copyfile(request.param, project_file)
    return request.param


def test_load_project(service: ProjectService, project_file: pathlib.Path):
    service.configure(platform=None, build_for=None)
    project = service.get()

    with project_file.with_suffix(".out").open() as f:
        expected = yaml.safe_yaml_load(f)

    assert project.marshal() == expected


@pytest.fixture(
    params=[
        pytest.param(path, id=path.name)
        for path in PROJECT_FILES_PATH.glob("overlaycraft-*.yaml")
    ]
)
def overlay_project_file(
    project_path: pathlib.Path, app_metadata, request: pytest.FixtureRequest
):
    project_file = project_path / f"{app_metadata.name}.yaml"
    shutil.copyfile(request.param, project_file)
    return request.param


@pytest.mark.usefixtures("enable_overlay")
def test_load_overlay_project(service: ProjectService, overlay_project_file):
    service.configure(platform=None, build_for=None)
    project = service.get()

    with overlay_project_file.with_suffix(".out").open() as f:
        expected = yaml.safe_yaml_load(f)

    assert project.marshal() == expected


@pytest.fixture(
    params=[
        pytest.param(path, id=path.name)
        for path in PROJECT_FILES_PATH.glob("grammarcraft-*.yaml")
    ]
)
def grammar_project_file(
    project_path: pathlib.Path, app_metadata, request: pytest.FixtureRequest
):
    project_file = project_path / f"{app_metadata.name}.yaml"
    shutil.copyfile(request.param, project_file)
    return request.param


@pytest.mark.parametrize("build_for", ["riscv64", "s390x"])
@pytest.mark.parametrize("build_on", ["amd64", "riscv64"])
def test_load_grammar_project(
    mocker, service: ProjectService, grammar_project_file, build_on, build_for
):
    mocker.patch(
        "craft_platforms.DebianArchitecture.from_host",
        return_value=craft_platforms.DebianArchitecture(build_on),
    )

    service.configure(build_for=build_for, platform=None)
    project = service.get()

    with grammar_project_file.with_suffix(
        f".on-{build_on}.for-{build_for}"
    ).open() as f:
        expected = yaml.safe_yaml_load(f)

    assert project.marshal() == expected
