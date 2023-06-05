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
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for BaseProject"""
import pathlib

import pytest
from craft_application.errors import CraftValidationError, ProjectFileMissingError
from craft_application.models import Project

PROJECTS_DIR = pathlib.Path(__file__).parent / "project_models"
PARTS_DICT = {"my-part": {"plugin": "nil"}}
BASIC_PROJECT = Project(
    name="project-name",
    version="1.0",
    parts=PARTS_DICT,
)
BASIC_PROJECT_DICT = {
    "name": "project-name",
    "version": "1.0",
    "parts": PARTS_DICT,
}
FULL_PROJECT = Project(
    name="full-project",
    title="A fully-defined project",
    base="core24",
    version="1.0.0.post64+git12345678",
    contact="author@project.org",
    issues="https://github.com/canonical/craft-application/issues",
    source_code="https://github.com/canonical/craft-application",
    summary="A fully-defined craft-application project.",
    description="A fully-defined craft-application project. (description)",
    license="LGPLv3",
    parts=PARTS_DICT,
)
FULL_PROJECT_DICT = {
    "base": "core24",
    "contact": "author@project.org",
    "description": "A fully-defined craft-application project. (description)",
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
    ["project", "project_dict"],
    [(BASIC_PROJECT, BASIC_PROJECT_DICT), (FULL_PROJECT, FULL_PROJECT_DICT)],
)
def test_marshal(project, project_dict):
    assert project.marshal() == project_dict


@pytest.mark.parametrize(
    ["project", "project_dict"],
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


@pytest.mark.parametrize(
    ["project_file", "expected"],
    [
        (PROJECTS_DIR / "basic_project.yaml", BASIC_PROJECT),
        (PROJECTS_DIR / "full_project.yaml", FULL_PROJECT),
    ],
)
def test_from_file_success(project_file, expected):
    with project_file.open():
        actual = Project.from_file(project_file)

    assert expected == actual


@pytest.mark.parametrize(
    ["project_file", "error_class"],
    [
        (PROJECTS_DIR / "nonexistent.yaml", ProjectFileMissingError),
        (PROJECTS_DIR / "invalid_project.yaml", CraftValidationError),
    ],
)
def test_from_file_failure(project_file, error_class):
    with pytest.raises(error_class):
        Project.from_file(project_file)


@pytest.mark.parametrize("project", [FULL_PROJECT])
def test_effective_base_is_base(project):
    assert project.effective_base == project.base


class FakeBuildBaseProject(Project):
    build_base: str


BUILD_BASE_PROJECT = FakeBuildBaseProject(
    name="project-name", version="1.0", parts={}, base="incorrect", build_base="correct"
)


@pytest.mark.parametrize("project", [BUILD_BASE_PROJECT])
def test_effective_base_is_build_base(project):
    assert project.effective_base == project.build_base