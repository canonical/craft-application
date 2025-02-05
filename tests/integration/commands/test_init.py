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
import os
import pathlib
import sys
import textwrap

import pytest

from craft_application.commands import InitCommand

# init operates in the current working directory
pytestmark = pytest.mark.usefixtures("new_dir")


@pytest.fixture(autouse=True)
def mock_parent_template_dir(tmp_path, mocker):
    """Mock the parent template directory."""
    mocker.patch.object(
        InitCommand,
        "parent_template_dir",
        pathlib.Path(tmp_path) / "templates",
    )


@pytest.fixture
def fake_template_dirs(tmp_path):
    """Set up a fake template directories with two templates.

    These templates are very simple because the InitService tests focus on the
    templates themselves.
    """
    parent_template_dir = tmp_path / "templates"

    simple_template_file = parent_template_dir / "simple" / "simple-file.j2"
    simple_template_file.parent.mkdir(parents=True)
    simple_template_file.write_text("name={{ name }}")

    other_template_file = parent_template_dir / "other-template" / "other-file.j2"
    other_template_file.parent.mkdir(parents=True)
    other_template_file.write_text("name={{ name }}")


@pytest.mark.parametrize(
    ("profile", "expected_file"),
    [
        (None, pathlib.Path("simple-file")),
        ("simple", pathlib.Path("simple-file")),
        ("other-template", pathlib.Path("other-file")),
    ],
)
@pytest.mark.parametrize("project_dir", [None, "project-dir"])
@pytest.mark.usefixtures("fake_template_dirs")
def test_init(
    app,
    capsys,
    monkeypatch,
    profile,
    expected_file,
    project_dir,
    empty_working_directory,
):
    """Initialise a project."""
    monkeypatch.chdir(empty_working_directory)
    expected_output = "Successfully initialised project"
    command = ["testcraft", "init"]
    if profile:
        command.extend(["--profile", profile])
    if project_dir:
        command.append(project_dir)
        expected_file = pathlib.Path(project_dir) / expected_file
    monkeypatch.setattr("sys.argv", command)

    return_code = app.run()
    stdout, _ = capsys.readouterr()

    assert return_code == os.EX_OK
    assert expected_output in stdout
    assert expected_file.is_file()
    # name is not provided, so use the project directory name
    assert f"name={expected_file.resolve().parent.name}" == expected_file.read_text()


@pytest.mark.usefixtures("fake_template_dirs")
@pytest.mark.parametrize(
    ("project_dir", "expected_file"),
    [
        (None, pathlib.Path("simple-file")),
        ("project-dir", pathlib.Path("project-dir") / "simple-file"),
    ],
)
def test_init_name(app, capsys, monkeypatch, project_dir, expected_file):
    """Initialise a project with a name."""
    expected_output = "Successfully initialised project"
    command = ["testcraft", "init", "--name", "test-project-name"]
    if project_dir:
        command.append(project_dir)
    monkeypatch.setattr("sys.argv", command)

    return_code = app.run()
    stdout, _ = capsys.readouterr()

    assert return_code == os.EX_OK
    assert expected_output in stdout
    assert expected_file.is_file()
    assert expected_file.read_text() == "name=test-project-name"


@pytest.mark.usefixtures("fake_template_dirs")
def test_init_invalid_profile(app, capsys, monkeypatch):
    """Give a helpful error message for invalid profiles."""
    choices = "other-template, simple"
    if sys.version_info < (3, 12, 8):
        choices = "'other-template', 'simple'"
    expected_error = (
        f"Error: argument --profile: invalid choice: 'bad' (choose from {choices})"
    )
    monkeypatch.setattr("sys.argv", ["testcraft", "init", "--profile", "bad"])

    return_code = app.run()
    _, stderr = capsys.readouterr()

    assert return_code == os.EX_USAGE
    assert expected_error in stderr


@pytest.mark.usefixtures("fake_template_dirs")
def test_init_overlapping_file(app, capsys, monkeypatch, tmp_path):
    """Give a helpful error message if a file would be overwritten."""
    pathlib.Path("simple-file").touch()
    expected_error = textwrap.dedent(
        f"""
        Cannot initialise project in {str(tmp_path)!r} because it would overwrite existing files.
        Existing files are:
          - simple-file
        Recommended resolution: Initialise the project in an empty directory or remove the existing files."""
    )
    monkeypatch.setattr("sys.argv", ["testcraft", "init", "--profile", "simple"])

    return_code = app.run()
    _, stderr = capsys.readouterr()

    assert return_code == os.EX_CANTCREAT
    assert expected_error in stderr


@pytest.mark.usefixtures("fake_template_dirs")
def test_init_nonoverlapping_file(app, capsys, monkeypatch):
    """Files can exist in the project directory if they won't be overwritten."""
    expected_output = "Successfully initialised project"
    pathlib.Path("unrelated-file").touch()
    monkeypatch.setattr("sys.argv", ["testcraft", "init", "--profile", "simple"])

    return_code = app.run()
    stdout, _ = capsys.readouterr()

    assert return_code == os.EX_OK
    assert expected_output in stdout
    assert pathlib.Path("simple-file").is_file()


@pytest.mark.usefixtures("fake_template_dirs")
def test_init_invalid_directory(app, monkeypatch, tmp_path):
    """A default name is used if the project dir is not a valid project name."""
    invalid_dir = tmp_path / "invalid--name"
    invalid_dir.mkdir()
    monkeypatch.chdir(invalid_dir)

    monkeypatch.setattr("sys.argv", ["testcraft", "init", "--profile", "simple"])
    return_code = app.run()

    assert return_code == os.EX_OK
    expected_file = invalid_dir / "simple-file"
    assert expected_file.read_text() == "name=my-project"
