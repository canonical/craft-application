# This file is part of craft-application.
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
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for BaseProject"""
import pathlib
from textwrap import dedent
from typing import Optional

import pytest
from craft_application import util
from craft_application.errors import CraftValidationError
from craft_application.models import Project

PROJECTS_DIR = pathlib.Path(__file__).parent / "project_models"
PARTS_DICT = {"my-part": {"plugin": "nil"}}
# pyright doesn't like these types and doesn't have a pydantic plugin like mypy.
# Because of this, we need to silence several errors in these constants.
BASIC_PROJECT = Project(
    name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
    version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
    parts=PARTS_DICT,
)
BASIC_PROJECT_DICT = {
    "name": "project-name",
    "version": "1.0",
    "parts": PARTS_DICT,
}
FULL_PROJECT = Project(
    name="full-project",  # pyright: ignore[reportGeneralTypeIssues]
    title="A fully-defined project",  # pyright: ignore[reportGeneralTypeIssues]
    base="core24",
    version="1.0.0.post64+git12345678",  # pyright: ignore[reportGeneralTypeIssues]
    contact="author@project.org",
    issues="https://github.com/canonical/craft-application/issues",
    source_code="https://github.com/canonical/craft-application",  # pyright: ignore[reportGeneralTypeIssues]
    summary="A fully-defined craft-application project.",  # pyright: ignore[reportGeneralTypeIssues]
    description="A fully-defined craft-application project.\nWith more than one line.\n",
    license="LGPLv3",
    parts=PARTS_DICT,
)
FULL_PROJECT_DICT = {
    "base": "core24",
    "contact": "author@project.org",
    "description": dedent(
        """\
        A fully-defined craft-application project.
        With more than one line.
    """
    ),
    "issues": "https://github.com/canonical/craft-application/issues",
    "license": "LGPLv3",
    "name": "full-project",
    "parts": PARTS_DICT,
    "source-code": "https://github.com/canonical/craft-application",
    "summary": "A fully-defined craft-application project.",
    "title": "A fully-defined project",
    "version": "1.0.0.post64+git12345678",
}


@pytest.mark.parametrize(
    ("project", "project_dict"),
    [(BASIC_PROJECT, BASIC_PROJECT_DICT), (FULL_PROJECT, FULL_PROJECT_DICT)],
)
def test_marshal(project, project_dict):
    assert project.marshal() == project_dict


@pytest.mark.parametrize(
    ("project", "project_dict"),
    [(BASIC_PROJECT, BASIC_PROJECT_DICT), (FULL_PROJECT, FULL_PROJECT_DICT)],
)
def test_unmarshal_success(project, project_dict):
    assert Project.unmarshal(project_dict) == project


@pytest.mark.parametrize("data", [None, [], (), 0, ""])
def test_unmarshal_error(data):
    with pytest.raises(TypeError):
        Project.unmarshal(data)


@pytest.mark.parametrize("project", [BASIC_PROJECT, FULL_PROJECT])
def test_marshal_then_unmarshal(project):
    assert Project.unmarshal(project.marshal()) == project


@pytest.mark.parametrize("project_dict", [BASIC_PROJECT_DICT, FULL_PROJECT_DICT])
def test_unmarshal_then_marshal(project_dict):
    assert Project.unmarshal(project_dict).marshal() == project_dict


@pytest.mark.parametrize("project", [BASIC_PROJECT, FULL_PROJECT])
def test_build_plan_not_implemented(project):
    with pytest.raises(NotImplementedError):
        project.get_build_plan()


@pytest.mark.parametrize(
    ("project_file", "expected"),
    [
        (PROJECTS_DIR / "basic_project.yaml", BASIC_PROJECT),
        (PROJECTS_DIR / "full_project.yaml", FULL_PROJECT),
    ],
)
def test_from_yaml_file_success(project_file, expected):
    with project_file.open():
        actual = Project.from_yaml_file(project_file)

    assert expected == actual


@pytest.mark.parametrize(
    ("project_file", "error_class"),
    [
        (PROJECTS_DIR / "nonexistent.yaml", FileNotFoundError),
        (PROJECTS_DIR / "invalid_project.yaml", CraftValidationError),
    ],
)
def test_from_yaml_file_failure(project_file, error_class):
    with pytest.raises(error_class):
        Project.from_yaml_file(project_file)


@pytest.mark.parametrize(
    ("project_file", "expected"),
    [
        (PROJECTS_DIR / "basic_project.yaml", BASIC_PROJECT),
        (PROJECTS_DIR / "full_project.yaml", FULL_PROJECT),
    ],
)
def test_from_yaml_data_success(project_file, expected):
    with project_file.open() as file:
        data = util.safe_yaml_load(file)

    actual = Project.from_yaml_data(data, project_file)

    assert expected == actual


@pytest.mark.parametrize(
    ("project_file", "error_class"),
    [
        (PROJECTS_DIR / "invalid_project.yaml", CraftValidationError),
    ],
)
def test_from_yaml_data_failure(project_file, error_class):
    with project_file.open() as file:
        data = util.safe_yaml_load(file)

    with pytest.raises(error_class):
        Project.from_yaml_data(data, project_file)


@pytest.mark.parametrize(
    ("project", "expected_file"),
    [
        (BASIC_PROJECT, PROJECTS_DIR / "basic_project.yaml"),
        (FULL_PROJECT, PROJECTS_DIR / "full_project.yaml"),
    ],
)
def test_to_yaml_file(project, expected_file, tmp_path):
    actual_file = tmp_path / "out.yaml"

    project.to_yaml_file(actual_file)

    assert actual_file.read_text() == expected_file.read_text()


@pytest.mark.parametrize("project", [FULL_PROJECT])
def test_effective_base_is_base(project):
    assert project.effective_base == project.base


class FakeBuildBaseProject(Project):
    build_base: Optional[str]


# As above, we need to tell pyright to ignore several typing issues.
BUILD_BASE_PROJECT = FakeBuildBaseProject(
    name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
    version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
    parts={},
    base="incorrect",
    build_base="correct",
)


@pytest.mark.parametrize("project", [BUILD_BASE_PROJECT])
def test_effective_base_is_build_base(project):
    assert project.effective_base == project.build_base


def test_effective_base_unknown():
    project = FakeBuildBaseProject(
        name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
        version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
        parts={},
        base=None,
        build_base=None,
    )

    with pytest.raises(RuntimeError) as exc_info:
        _ = project.effective_base

    assert exc_info.match("Could not determine effective base")
