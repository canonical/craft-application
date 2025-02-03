# This file is part of craft-application.
#
# Copyright 2024 Canonical Ltd.
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

"""Tests for init command."""

import argparse
import pathlib

import pytest

from craft_application.commands import InitCommand
from craft_application.errors import InitError

# init operates in the current working directory
pytestmark = pytest.mark.usefixtures("new_dir")


@pytest.fixture
def init_command(app_metadata, mock_services, mocker, tmp_path):
    mocker.patch.object(
        InitCommand,
        "parent_template_dir",
        pathlib.Path(tmp_path) / "templates",
    )
    return InitCommand({"app": app_metadata, "services": mock_services})


@pytest.fixture
def fake_template_dirs(tmp_path):
    """Set up a fake template directories with two templates.

    These templates are very simple because tests focused on the templates themselves
    are in the InitService tests.
    """
    parent_template_dir = tmp_path / "templates"

    (parent_template_dir / "simple").mkdir(parents=True)
    (parent_template_dir / "other-template").mkdir()

    return parent_template_dir


@pytest.mark.parametrize("name", [None, "my-project"])
def test_init_in_cwd(init_command, name, new_dir, mock_services, emitter):
    """Test the init command in the current working directory."""
    expected_name = name or new_dir.name
    parsed_args = argparse.Namespace(
        project_dir=None,
        name=name,
        profile="test-profile",
    )
    mock_services.init.validate_project_name.return_value = expected_name

    init_command.run(parsed_args)

    mock_services.init.initialise_project.assert_called_once_with(
        project_dir=new_dir,
        project_name=expected_name,
        template_dir=init_command.parent_template_dir / "test-profile",
    )
    emitter.assert_message("Successfully initialised project.")


@pytest.mark.parametrize("name", [None, "my-project"])
def test_init_run_project_dir(init_command, name, mock_services, emitter):
    """Test the init command in a project directory."""
    expected_name = name or "test-project-dir"
    project_dir = pathlib.Path("test-project-dir")
    parsed_args = argparse.Namespace(
        project_dir=project_dir,
        name=name,
        profile="test-profile",
    )
    mock_services.init.validate_project_name.return_value = expected_name

    init_command.run(parsed_args)

    mock_services.init.initialise_project.assert_called_once_with(
        project_dir=project_dir.expanduser().resolve(),
        project_name=expected_name,
        template_dir=init_command.parent_template_dir / "test-profile",
    )
    emitter.assert_message("Successfully initialised project.")


@pytest.mark.usefixtures("fake_template_dirs")
def test_profiles(init_command):
    """Test profile generation."""
    assert init_command.default_profile == "simple"
    assert init_command.profiles == ["other-template", "simple"]


def test_existing_files(init_command, tmp_path, mock_services):
    """Error if the check for existing files fails."""
    mock_services.init.check_for_existing_files.side_effect = InitError("test-error")
    parsed_args = argparse.Namespace(
        project_dir=tmp_path,
        name="test-project-name",
        profile="test-profile",
    )

    with pytest.raises(InitError, match="test-error"):
        init_command.run(parsed_args)

    mock_services.init.initialise_project.assert_not_called()


def test_invalid_name(init_command, mock_services):
    mock_services.init.validate_project_name.side_effect = InitError("test-error")
    parsed_args = argparse.Namespace(
        name="invalid--name",
    )
    with pytest.raises(InitError, match="test-error"):
        init_command.run(parsed_args)


def test_invalid_name_directory(init_command, mock_services):
    def _validate_project_name(_name: str, *, use_default: bool = False):
        if use_default:
            return "my-project"
        raise InitError("test-error")

    mock_services.init.validate_project_name = _validate_project_name

    project_dir = pathlib.Path("invalid--name")
    parsed_args = argparse.Namespace(
        project_dir=project_dir,
        name=None,
        profile="simple",
    )

    init_command.run(parsed_args)

    mock_services.init.initialise_project.assert_called_once_with(
        project_dir=project_dir.expanduser().resolve(),
        project_name="my-project",
        template_dir=init_command.parent_template_dir / "simple",
    )
