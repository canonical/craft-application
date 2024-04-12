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
    CURRENT_DEVEL_BASE,
    DEVEL_BASE,
    BuildPlanner,
    Project,
    constraints,
)
from typing_extensions import override

PROJECTS_DIR = pathlib.Path(__file__).parent / "project_models"
PARTS_DICT = {"my-part": {"plugin": "nil"}}


@pytest.fixture()
def basic_project(fake_project_class):
    # pyright doesn't like these types and doesn't have a pydantic plugin like mypy.
    # Because of this, we need to silence several errors in these constants.
    return fake_project_class(  # pyright: ignore[reportCallIssue]
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
def full_project(fake_project_class):
    return fake_project_class(  # pyright: ignore[reportCallIssue]
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
def test_unmarshal_success(project_fixture, project_dict, fake_project_class, request):
    project = request.getfixturevalue(project_fixture)

    assert fake_project_class.unmarshal(project_dict) == project


@pytest.mark.parametrize("data", [None, [], (), 0, ""])
def test_unmarshal_error(data, fake_project_class):
    with pytest.raises(TypeError):
        fake_project_class.unmarshal(data)


@pytest.mark.parametrize("project_fixture", ["basic_project", "full_project"])
def test_marshal_then_unmarshal(project_fixture, fake_project_class, request):
    project = request.getfixturevalue(project_fixture)

    assert fake_project_class.unmarshal(project.marshal()) == project


@pytest.mark.parametrize("project_dict", [BASIC_PROJECT_DICT, FULL_PROJECT_DICT])
def test_unmarshal_then_marshal(project_dict, fake_project_class):
    assert fake_project_class.unmarshal(project_dict).marshal() == project_dict


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
def test_from_yaml_file_success(
    project_file, expected_fixture, fake_project_class, request
):
    expected = request.getfixturevalue(expected_fixture)

    with project_file.open():
        actual = fake_project_class.from_yaml_file(project_file)

    assert expected == actual


@pytest.mark.parametrize(
    ("project_file", "error_class"),
    [
        (PROJECTS_DIR / "nonexistent.yaml", FileNotFoundError),
        (PROJECTS_DIR / "invalid_project.yaml", CraftValidationError),
    ],
)
def test_from_yaml_file_failure(project_file, error_class, fake_project_class):
    with pytest.raises(error_class):
        fake_project_class.from_yaml_file(project_file)


@pytest.mark.parametrize(
    ("project_file", "expected_fixture"),
    [
        (PROJECTS_DIR / "basic_project.yaml", "basic_project"),
        (PROJECTS_DIR / "full_project.yaml", "full_project"),
    ],
)
def test_from_yaml_data_success(
    project_file, expected_fixture, fake_project_class, request
):
    expected = request.getfixturevalue(expected_fixture)
    with project_file.open() as file:
        data = util.safe_yaml_load(file)

    actual = fake_project_class.from_yaml_data(data, project_file)

    assert expected == actual


@pytest.mark.parametrize(
    ("project_file", "error_class"),
    [
        (PROJECTS_DIR / "invalid_project.yaml", CraftValidationError),
    ],
)
def test_from_yaml_data_failure(project_file, error_class, fake_project_class):
    with project_file.open() as file:
        data = util.safe_yaml_load(file)

    with pytest.raises(error_class):
        fake_project_class.from_yaml_data(data, project_file)


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
    build_base: str | None

    @override
    @classmethod
    def _providers_base(
        cls, base: str | None
    ) -> craft_providers.bases.BaseAlias | None:
        """Get a BaseAlias from the application's base."""
        if not base:
            return None

        try:
            return craft_providers.bases.get_base_alias(("ubuntu", base))
        except craft_providers.errors.BaseConfigurationError:
            return None


def test_effective_base_is_build_base():
    base = craft_providers.bases.ubuntu.BuilddBaseAlias.JAMMY.value
    build_base = craft_providers.bases.ubuntu.BuilddBaseAlias.NOBLE.value

    # As above, we need to tell pyright to ignore several typing issues.
    project = FakeBuildBaseProject(  # pyright: ignore[reportCallIssue]
        name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
        version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
        parts={},
        base=base,
        build_base=build_base,
    )

    assert project.effective_base == build_base


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


def test_devel_base_devel_build_base():
    """Base can be 'devel' when the build-base is 'devel'."""
    _ = FakeBuildBaseProject(  # pyright: ignore[reportCallIssue]
        name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
        version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
        parts={},
        base=CURRENT_DEVEL_BASE.value,
        build_base=DEVEL_BASE.value,
    )


def test_devel_base_no_build_base():
    """Base can be 'devel' if the build-base is not set."""
    _ = FakeBuildBaseProject(  # pyright: ignore[reportCallIssue]
        name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
        version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
        parts={},
        base=CURRENT_DEVEL_BASE.value,
    )


def test_devel_base_error():
    """Raise an error if base is 'devel' and build-base is not 'devel'."""
    with pytest.raises(CraftValidationError) as exc_info:
        FakeBuildBaseProject(  # pyright: ignore[reportCallIssue]
            name="project-name",  # pyright: ignore[reportGeneralTypeIssues]
            version="1.0",  # pyright: ignore[reportGeneralTypeIssues]
            parts={},
            base=CURRENT_DEVEL_BASE.value,
            build_base=craft_providers.bases.ubuntu.BuilddBaseAlias.JAMMY.value,
        )

    assert exc_info.match(
        f"build-base must be 'devel' when base is '{CURRENT_DEVEL_BASE.value}'"
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
    full_project_dict, field_name, invalid_value, expected_message, fake_project_class
):
    """Test that invalid regex-based fields generate expected messages."""
    full_project_dict[field_name] = invalid_value
    project_path = pathlib.Path("myproject.yaml")

    with pytest.raises(CraftValidationError) as exc:
        fake_project_class.from_yaml_data(full_project_dict, project_path)

    full_expected_message = textwrap.dedent(
        f"""
        Bad myproject.yaml content:
        - {expected_message} (in field '{field_name}')
        """
    ).strip()

    message = str(exc.value)
    assert message == full_expected_message


def test_unmarshal_repositories(full_project_dict, fake_project_class):
    """Test that package-repositories are allowed in Project with package repositories feature."""
    full_project_dict["package-repositories"] = [{"ppa": "ppa/ppa", "type": "apt"}]
    project_path = pathlib.Path("myproject.yaml")
    project = fake_project_class.from_yaml_data(full_project_dict, project_path)

    assert project.package_repositories == [{"ppa": "ppa/ppa", "type": "apt"}]


def test_unmarshal_no_repositories(full_project_dict, fake_project_class):
    """Test that package-repositories are allowed to be None in Project with package repositories feature."""
    full_project_dict["package-repositories"] = None
    project_path = pathlib.Path("myproject.yaml")

    project = fake_project_class.from_yaml_data(full_project_dict, project_path)

    assert project.package_repositories is None


def test_unmarshal_undefined_repositories(full_project_dict, fake_project_class):
    """Test that package-repositories are allowed to not exist in Project with package repositories feature."""
    if "package-repositories" in full_project_dict:
        del full_project_dict["package-repositories"]

    project_path = pathlib.Path("myproject.yaml")

    project = fake_project_class.from_yaml_data(full_project_dict, project_path)

    assert project.package_repositories is None


def test_unmarshal_invalid_repositories(full_project_dict, fake_project_class):
    """Test that package-repositories are validated in Project with package repositories feature."""
    full_project_dict["package-repositories"] = [[]]
    project_path = pathlib.Path("myproject.yaml")

    with pytest.raises(CraftValidationError) as error:
        fake_project_class.from_yaml_data(full_project_dict, project_path)

    assert error.value.args[0] == (
        "Bad myproject.yaml content:\n"
        "- field 'type' required in 'package-repositories[0]' configuration\n"
        "- field 'url' required in 'package-repositories[0]' configuration\n"
        "- field 'key-id' required in 'package-repositories[0]' configuration"
    )
