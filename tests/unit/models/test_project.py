# This file is part of craft-application.
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
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for BaseProject"""
import copy
import pathlib
import textwrap
from textwrap import dedent

import craft_providers.bases
import pytest
from craft_application import util
from craft_application.errors import CraftValidationError
from craft_application.models import (
    DEVEL_BASE_INFOS,
    DEVEL_BASE_WARNING,
    BuildPlanner,
    Project,
    constraints,
)

PROJECTS_DIR = pathlib.Path(__file__).parent / "project_models"
PARTS_DICT = {"my-part": {"plugin": "nil"}}


@pytest.fixture()
def basic_project():
    # pyright doesn't like these types and doesn't have a pydantic plugin like mypy.
    # Because of this, we need to silence several errors in these constants.
    return Project(  # pyright: ignore[reportCallIssue]
        name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
        version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
        parts=PARTS_DICT,
    )


BASIC_PROJECT_DICT = {
    "name": "project-name",
    "version": "1.0",
    "parts": PARTS_DICT,
}


@pytest.fixture()
def full_project():
    return Project(  # pyright: ignore[reportCallIssue]
        name="full-project",  # pyright: ignore[reportGeneralTypeIssues]
        title="A fully-defined project",  # pyright: ignore[reportGeneralTypeIssues]
        base="ubuntu@24.04",
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
    "base": "ubuntu@24.04",
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
    ("project_fixture", "project_dict"),
    [("basic_project", BASIC_PROJECT_DICT), ("full_project", FULL_PROJECT_DICT)],
)
def test_marshal(project_fixture, project_dict, request):
    project = request.getfixturevalue(project_fixture)

    assert project.marshal() == project_dict


@pytest.mark.parametrize(
    ("project_fixture", "project_dict"),
    [("basic_project", BASIC_PROJECT_DICT), ("full_project", FULL_PROJECT_DICT)],
)
def test_unmarshal_success(project_fixture, project_dict, request):
    project = request.getfixturevalue(project_fixture)

    assert Project.unmarshal(project_dict) == project


@pytest.mark.parametrize("data", [None, [], (), 0, ""])
def test_unmarshal_error(data):
    with pytest.raises(TypeError):
        Project.unmarshal(data)


@pytest.mark.parametrize("project_fixture", ["basic_project", "full_project"])
def test_marshal_then_unmarshal(project_fixture, request):
    project = request.getfixturevalue(project_fixture)

    assert Project.unmarshal(project.marshal()) == project


@pytest.mark.parametrize("project_dict", [BASIC_PROJECT_DICT, FULL_PROJECT_DICT])
def test_unmarshal_then_marshal(project_dict):
    assert Project.unmarshal(project_dict).marshal() == project_dict


def test_build_planner_abstract():
    with pytest.raises(TypeError):
        BuildPlanner()  # type: ignore[type-abstract]


@pytest.mark.parametrize(
    ("project_file", "expected_fixture"),
    [
        (PROJECTS_DIR / "basic_project.yaml", "basic_project"),
        (PROJECTS_DIR / "full_project.yaml", "full_project"),
    ],
)
def test_from_yaml_file_success(project_file, expected_fixture, request):
    expected = request.getfixturevalue(expected_fixture)

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
    ("project_file", "expected_fixture"),
    [
        (PROJECTS_DIR / "basic_project.yaml", "basic_project"),
        (PROJECTS_DIR / "full_project.yaml", "full_project"),
    ],
)
def test_from_yaml_data_success(project_file, expected_fixture, request):
    expected = request.getfixturevalue(expected_fixture)
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
    ("project_fixture", "expected_file"),
    [
        ("basic_project", PROJECTS_DIR / "basic_project.yaml"),
        ("full_project", PROJECTS_DIR / "full_project.yaml"),
    ],
)
def test_to_yaml_file(project_fixture, expected_file, tmp_path, request):
    project = request.getfixturevalue(project_fixture)
    actual_file = tmp_path / "out.yaml"

    project.to_yaml_file(actual_file)

    assert actual_file.read_text() == expected_file.read_text()


def test_effective_base_is_base(full_project):
    assert full_project.effective_base == full_project.base


class FakeBuildBaseProject(Project):
    build_base: str | None  # pyright: ignore[reportGeneralTypeIssues]


def test_effective_base_is_build_base():
    # As above, we need to tell pyright to ignore several typing issues.
    project = FakeBuildBaseProject(  # pyright: ignore[reportCallIssue]
        name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
        version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
        parts={},
        base="ubuntu@22.04",
        build_base="ubuntu@24.04",
    )

    assert project.effective_base == "ubuntu@24.04"


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


def test_devel_base_devel_build_base(emitter):
    """Base can be 'devel' when the build-base is 'devel'."""
    _ = FakeBuildBaseProject(  # pyright: ignore[reportCallIssue]
        name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
        version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
        parts={},
        base=f"ubuntu@{DEVEL_BASE_INFOS[0].current_devel_base.value}",
        build_base=f"ubuntu@{DEVEL_BASE_INFOS[0].current_devel_base.value}",
    )

    emitter.assert_message(DEVEL_BASE_WARNING)


def test_devel_base_no_base():
    """Do not validate the build-base if there is no base."""
    _ = FakeBuildBaseProject(  # pyright: ignore[reportCallIssue]
        name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
        version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
        parts={},
    )


def test_devel_base_no_base_alias(mocker):
    """Do not validate the build base if there is no base alias."""
    mocker.patch(
        "tests.unit.models.test_project.FakeBuildBaseProject._providers_base",
        return_value=None,
    )

    _ = FakeBuildBaseProject(  # pyright: ignore[reportCallIssue]
        name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
        version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
        parts={},
    )


def test_devel_base_no_build_base():
    """Base can be 'devel' if the build-base is not set."""
    _ = FakeBuildBaseProject(  # pyright: ignore[reportCallIssue]
        name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
        version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
        parts={},
        base=f"ubuntu@{DEVEL_BASE_INFOS[0].current_devel_base.value}",
    )


def test_devel_base_error():
    """Raise an error if base is 'devel' and build-base is not 'devel'."""
    with pytest.raises(CraftValidationError) as exc_info:
        FakeBuildBaseProject(  # pyright: ignore[reportCallIssue]
            name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
            version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
            parts={},
            base=f"ubuntu@{DEVEL_BASE_INFOS[0].current_devel_base.value}",
            build_base=f"ubuntu@{craft_providers.bases.ubuntu.BuilddBaseAlias.JAMMY.value}",
        )

    assert exc_info.match(
        f"A development build-base must be used when base is 'ubuntu@{DEVEL_BASE_INFOS[0].current_devel_base.value}'"
    )


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
