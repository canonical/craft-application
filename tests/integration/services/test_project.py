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
import textwrap
from typing import Any

import craft_platforms
import pytest
from craft_application.errors import CraftValidationError
from craft_application.services.project import ProjectService
from craft_application.util import yaml
from typing_extensions import override

PROJECT_FILES_PATH = pathlib.Path(__file__).parent / "project_files"
INVALID_PROJECT_FILES_PATH = pathlib.Path(__file__).parent / "invalid_project_files"


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


@pytest.fixture(
    params=[
        pytest.param(path, id=path.name)
        for path in INVALID_PROJECT_FILES_PATH.glob("testcraft-*.yaml")
    ]
)
def invalid_project_file(
    project_path: pathlib.Path, app_metadata, request: pytest.FixtureRequest
):
    project_file = project_path / f"{app_metadata.name}.yaml"
    shutil.copyfile(request.param, project_file)
    return request.param


def test_load_invalid_project(
    service: ProjectService, invalid_project_file: pathlib.Path
):
    error_file = invalid_project_file.with_suffix(".error")
    error_regex = error_file.read_text().rstrip()

    service.configure(platform=None, build_for=None)

    with pytest.raises(CraftValidationError, match=error_regex):
        service.get()


class PartInjectingProjectService(ProjectService):
    """A ProjectService that injects an app-only part name into the project."""

    @override
    @staticmethod
    def _app_preprocess_project(
        project: dict[str, Any],
        *,
        build_on: str,
        build_for: str,
        platform: str,
    ) -> None:
        project.setdefault("parts", {})["mycraft/some-part"] = {"plugin": "nil"}


@pytest.mark.parametrize("base", ["ubuntu@24.04", "ubuntu@26.04", "unknown@base"])
def test_inject_app_only_part(
    tmp_path, app_metadata, fake_services, in_project_path: pathlib.Path, base: str
):
    """Test that the app can add a part that contains a name that a user cannot."""
    project_path = tmp_path / f"{app_metadata.name}.yaml"
    project_path.write_text(
        textwrap.dedent(
            f"""\
            name: my-project
            adopt-info: my-part
            platforms:
              riscv64:
            base: {base}
            parts:
              my-part:
                plugin: nil
            """
        )
    )

    service = PartInjectingProjectService(
        app_metadata,
        fake_services,
        project_dir=tmp_path,
    )
    service.setup()
    service.configure(platform=None, build_for=None)

    project = service.get()

    assert "my-part" in project.parts
    assert "mycraft/some-part" in project.parts
