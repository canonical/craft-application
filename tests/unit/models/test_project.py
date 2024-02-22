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
import copy
import pathlib
import textwrap
from textwrap import dedent

import pytest
from craft_application import util
from craft_application.errors import CraftValidationError
from craft_application.models import BuildPlanner, Project, constraints

PROJECTS_DIR = pathlib.Path(__file__).parent / "project_models"
PARTS_DICT = {"my-part": {"plugin": "nil"}}
# pyright doesn't like these types and doesn't have a pydantic plugin like mypy.
# Because of this, we need to silence several errors in these constants.
BASIC_PROJECT = Project(  # pyright: ignore[reportCallIssue]
    name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
    version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
    parts=PARTS_DICT,
)
BASIC_PROJECT_DICT = {
    "name": "project-name",
    "version": "1.0",
    "parts": PARTS_DICT,
}
FULL_PROJECT = Project(  # pyright: ignore[reportCallIssue]
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


@pytest.fixture()
def full_project_dict():
    """Provides a modifiable copy of ``FULL_PROJECT_DICT``"""
    return copy.deepcopy(FULL_PROJECT_DICT)


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


def test_build_planner_abstract():
    with pytest.raises(TypeError):
        BuildPlanner()  # type: ignore[type-abstract]


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
    build_base: str | None


# As above, we need to tell pyright to ignore several typing issues.
BUILD_BASE_PROJECT = FakeBuildBaseProject(  # pyright: ignore[reportCallIssue]
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
    project = FakeBuildBaseProject(  # pyright: ignore[reportCallIssue]
        name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
        version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
        parts={},
        base=None,
        build_base=None,
    )

    with pytest.raises(RuntimeError) as exc_info:
        _ = project.effective_base

    assert exc_info.match("Could not determine effective base")


@pytest.mark.parametrize(
    ("field_name", "invalid_value", "expected_message"),
    [
        pytest.param(
            "version",
            "invalid_version",
            constraints.MESSAGE_INVALID_VERSION,
            id="version",
        ),
        pytest.param(
            "name", "invalid_name", constraints.MESSAGE_INVALID_NAME, id="name"
        ),
    ],
)
def test_invalid_field_message(
    full_project_dict, field_name, invalid_value, expected_message
):
    """Test that invalid regex-based fields generate expected messages."""
    full_project_dict[field_name] = invalid_value
    project_path = pathlib.Path("myproject.yaml")

    with pytest.raises(CraftValidationError) as exc:
        Project.from_yaml_data(full_project_dict, project_path)

    full_expected_message = textwrap.dedent(
        f"""
        Bad myproject.yaml content:
        - {expected_message} (in field '{field_name}')
        """
    ).strip()

    message = str(exc.value)
    assert message == full_expected_message


def test_unmarshal_repositories(full_project_dict):
    """Test that package-repositories are allowed in Project with package repositories feature."""
    full_project_dict["package-repositories"] = [{"ppa": "ppa/ppa", "type": "apt"}]
    project_path = pathlib.Path("myproject.yaml")
    project = Project.from_yaml_data(full_project_dict, project_path)

    assert project.package_repositories == [{"ppa": "ppa/ppa", "type": "apt"}]


def test_unmarshal_no_repositories(full_project_dict):
    """Test that package-repositories are allowed to be None in Project with package repositories feature."""
    full_project_dict["package-repositories"] = None
    project_path = pathlib.Path("myproject.yaml")

    project = Project.from_yaml_data(full_project_dict, project_path)

    assert project.package_repositories is None


def test_unmarshal_undefined_repositories(full_project_dict):
    """Test that package-repositories are allowed to not exist in Project with package repositories feature."""
    if "package-repositories" in full_project_dict:
        del full_project_dict["package-repositories"]

    project_path = pathlib.Path("myproject.yaml")

    project = Project.from_yaml_data(full_project_dict, project_path)

    assert project.package_repositories is None


def test_unmarshal_invalid_repositories(full_project_dict):
    """Test that package-repositories are validated in Project with package repositories feature."""
    full_project_dict["package-repositories"] = [[]]
    project_path = pathlib.Path("myproject.yaml")

    with pytest.raises(CraftValidationError) as error:
        Project.from_yaml_data(full_project_dict, project_path)

    assert error.value.args[0] == (
        "Bad myproject.yaml content:\n"
        "- field 'type' required in 'package-repositories[0]' configuration\n"
        "- field 'url' required in 'package-repositories[0]' configuration\n"
        "- field 'key-id' required in 'package-repositories[0]' configuration"
    )
