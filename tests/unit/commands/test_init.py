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

# init operates in the current working directory
pytestmark = pytest.mark.usefixtures("new_dir")


@pytest.fixture
def init_command(app_metadata, mock_services):
    return InitCommand({"app": app_metadata, "services": mock_services})


@pytest.mark.parametrize("name", [None, "my-project"])
def test_init_in_cwd(init_command, name, new_dir, mock_services):
    """Test the init command in the current working directory."""
    expected_name = name or new_dir.name
    parsed_args = argparse.Namespace(project_dir=None, name=name)

    init_command.run(parsed_args)

    mock_services.init.run.assert_called_once_with(
        project_dir=new_dir, name=expected_name
    )


@pytest.mark.parametrize("name", [None, "my-project"])
def test_init_run_project_dir(init_command, name, mock_services):
    """Test the init command in a project directly."""
    expected_name = name or "test-project-dir"
    project_dir = pathlib.Path("test-project-dir")
    parsed_args = argparse.Namespace(project_dir=project_dir, name=name)

    init_command.run(parsed_args)

    mock_services.init.run.assert_called_once_with(
        project_dir=project_dir, name=expected_name
    )
