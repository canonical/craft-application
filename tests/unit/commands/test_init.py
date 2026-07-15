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


def test_profiles_excludes_base_variants(init_command, fake_template_dirs):
    """Base-specific template variants are not exposed as profiles."""
    (fake_template_dirs / "simple__ubuntu@22.04").mkdir()

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


def test_invalid_base_variant(init_command, tmp_path, mock_services):
    """Error if a requested base-specific variant does not exist."""
    (init_command.parent_template_dir / "simple__ubuntu@22.04").mkdir(parents=True)
    parsed_args = argparse.Namespace(
        project_dir=tmp_path,
        name="test-project-name",
        profile="simple",
        base="ubuntu@23.04",
    )

    with pytest.raises(InitError, match="Base variant 'ubuntu@23.04'") as exc_info:
        init_command.run(parsed_args)

    assert exc_info.value.resolution == (
        "Choose a different base for this profile.\n"
        "Available bases are: 'ubuntu@22.04'"
    )
    mock_services.init.initialise_project.assert_not_called()


def test_base_not_available_for_profile(init_command, tmp_path, mock_services):
    """Error if the selected profile has no base-specific variants."""
    parsed_args = argparse.Namespace(
        project_dir=tmp_path,
        name="test-project-name",
        profile="simple",
        base="ubuntu@22.04",
    )

    with pytest.raises(
        InitError, match="Base selection is not available for this profile."
    ) as exc_info:
        init_command.run(parsed_args)

    assert exc_info.value.resolution == (
        "Use this profile without --base, or choose a different profile."
    )
    mock_services.init.initialise_project.assert_not_called()


@pytest.mark.parametrize("base", ["ubuntu@22.04", "Ubuntu-22.04", "base-1.2@stable"])
def test_valid_base_name(init_command, fake_template_dirs, mock_services, emitter, base):
    """Allow supported characters in base-specific variant names."""
    (fake_template_dirs / f"simple__{base}").mkdir()
    parsed_args = argparse.Namespace(
        project_dir=None,
        name="test-project-name",
        profile="simple",
        base=base,
    )
    mock_services.init.validate_project_name.return_value = "test-project-name"

    init_command.run(parsed_args)

    mock_services.init.initialise_project.assert_called_once_with(
        project_dir=pathlib.Path.cwd().resolve(),
        project_name="test-project-name",
        template_dir=init_command.parent_template_dir / f"simple__{base}",
    )
    emitter.assert_message("Successfully initialised project.")


@pytest.mark.parametrize("base", ["ubuntu:22.04", "../../ubuntu@22.04"])
def test_invalid_base_name(init_command, tmp_path, mock_services, base):
    """Reject unsupported characters in base names."""
    parsed_args = argparse.Namespace(
        project_dir=tmp_path,
        name="test-project-name",
        profile="simple",
        base=base,
    )

    with pytest.raises(InitError, match="invalid base name"):
        init_command.run(parsed_args)

    mock_services.init.initialise_project.assert_not_called()


def test_valid_base_variant(init_command, fake_template_dirs, mock_services, emitter):
    """Use the base-specific template when the requested variant exists."""
    (fake_template_dirs / "simple__ubuntu@22.04").mkdir()
    parsed_args = argparse.Namespace(
        project_dir=None,
        name="test-project-name",
        profile="simple",
        base="ubuntu@22.04",
    )
    mock_services.init.validate_project_name.return_value = "test-project-name"

    init_command.run(parsed_args)

    mock_services.init.initialise_project.assert_called_once_with(
        project_dir=pathlib.Path.cwd().resolve(),
        project_name="test-project-name",
        template_dir=init_command.parent_template_dir / "simple__ubuntu@22.04",
    )
    emitter.assert_message("Successfully initialised project.")
