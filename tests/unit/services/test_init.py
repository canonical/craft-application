#  This file is part of craft-application.
#
#  Copyright 2024 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Unit tests for the InitService."""

import pathlib
from unittest import mock

import jinja2
import pytest
import pytest_check
from craft_application import services


@pytest.fixture
def init_service(app_metadata, fake_services):
    _init_service = services.InitService(app_metadata, fake_services)
    _init_service.setup()
    return _init_service


@pytest.fixture
def mock_template():
    _mock_template = mock.Mock(spec=jinja2.Template)
    _mock_template.render.return_value = "rendered content"
    return _mock_template


@pytest.fixture
def mock_environment(mock_template):
    _mock_environment = mock.Mock(spec=jinja2.Environment)
    _mock_environment.get_template.return_value = mock_template
    return _mock_environment


def test_get_context(init_service):
    context = init_service._get_context(name="my-project")

    assert context == {"name": "my-project"}


def test_get_template_dir(init_service):
    template_dir = init_service._get_template_dir()

    assert template_dir == pathlib.Path("templates")


def test_get_executable_files(init_service):
    executable_files = init_service._get_executable_files()

    assert executable_files == []


def test_create_project_dir(init_service, tmp_path, emitter):
    project_dir = tmp_path / "my-project"

    init_service._create_project_dir(project_dir=project_dir, name="my-project")

    assert project_dir.is_dir()
    emitter.assert_debug(f"Using project directory {str(project_dir)!r} for my-project")


def test_create_project_dir_exists(init_service, tmp_path, emitter):
    """Do not error if the project directory already exists."""
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()

    init_service._create_project_dir(project_dir=project_dir, name="my-project")

    assert project_dir.is_dir()
    emitter.assert_debug(f"Using project directory {str(project_dir)!r} for my-project")


def test_get_templates_environment(init_service, mocker):
    """Test that _get_templates_environment returns a Jinja2 environment."""
    mock_package_loader = mocker.patch("jinja2.PackageLoader")
    mock_environment = mocker.patch("jinja2.Environment")

    environment = init_service._get_templates_environment(pathlib.Path("test-dir"))

    mock_package_loader.assert_called_once_with("testcraft", "test-dir")
    mock_environment.assert_called_once_with(
        loader=mock_package_loader.return_value,
        autoescape=False,
        keep_trailing_newline=True,
        optimized=False,
        undefined=jinja2.StrictUndefined,
    )
    assert environment == mock_environment.return_value


@pytest.mark.parametrize("template_filename", ["file1.txt", "nested/file2.txt"])
def test_copy_template_file(init_service, tmp_path, template_filename):
    # create template
    template_dir = tmp_path / "templates"
    template_file = template_dir / template_filename
    template_file.parent.mkdir(parents=True, exist_ok=True)
    template_file.write_text("content")
    # create project with an existing file
    project_dir = tmp_path / "project"
    project_dir.mkdir()

    init_service._copy_template_file(template_filename, template_dir, project_dir)

    assert (project_dir / template_filename).read_text() == "content"


@pytest.mark.parametrize("template_name", ["file1.txt", "nested/file2.txt"])
def test_copy_template_file_exists(init_service, tmp_path, template_name, emitter):
    """Do not overwrite existing files."""
    # create template
    template_dir = tmp_path / "templates"
    template_file = template_dir / template_name
    template_file.parent.mkdir(parents=True, exist_ok=True)
    template_file.write_text("content")
    # create project with an existing file
    project_dir = tmp_path / "project"
    (project_dir / template_name).parent.mkdir(parents=True, exist_ok=True)
    (project_dir / template_name).write_text("existing content")

    init_service._copy_template_file(template_name, template_dir, project_dir)

    assert (project_dir / template_name).read_text() == "existing content"
    emitter.assert_debug(
        f"Skipping file {template_name} because it is already present."
    )


def test_render_project(init_service, tmp_path, mock_environment):
    template_filenames = [
        # Jinja2 templates
        "jinja-file.txt.j2",
        "nested/jinja-file.txt.j2",
        # Non-Jinja2 templates (regular files)
        "non-jinja-file.txt",
        "nested/non-jinja-file.txt",
    ]
    mock_environment.list_templates.return_value = template_filenames
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    template_dir = tmp_path / "templates"
    for filename in template_filenames:
        (template_dir / filename).parent.mkdir(parents=True, exist_ok=True)
        (template_dir / filename).write_text("template content")

    init_service._render_project(
        environment=mock_environment,
        project_dir=project_dir,
        template_dir=template_dir,
        context={"name": "my-project"},
        executable_files=[],
    )

    pytest_check.equal((project_dir / "jinja-file.txt").read_text(), "rendered content")
    pytest_check.equal(
        (project_dir / "nested/jinja-file.txt").read_text(), "rendered content"
    )
    pytest_check.equal(
        (project_dir / "non-jinja-file.txt").read_text(), "template content"
    )
    pytest_check.equal(
        (project_dir / "nested/non-jinja-file.txt").read_text(), "template content"
    )


def test_render_project_executable(init_service, tmp_path, mock_environment):
    template_filenames = [
        "executable-1.sh.j2",
        "executable-2.sh.j2",
        "executable-3.sh",
    ]
    mock_environment.list_templates.return_value = template_filenames
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    template_dir = tmp_path / "templates"
    for filename in template_filenames:
        (template_dir / filename).parent.mkdir(parents=True, exist_ok=True)
        (template_dir / filename).write_text("template content")

    init_service._render_project(
        environment=mock_environment,
        project_dir=project_dir,
        template_dir=template_dir,
        context={"name": "my-project"},
        executable_files=["executable-1.sh", "executable-3.sh"],
    )

    import os

    pytest_check.is_true(os.access(project_dir / "executable-1.sh", os.X_OK))
    pytest_check.is_false(os.access(project_dir / "executable-2.sh", os.X_OK))
    pytest_check.is_false(os.access(project_dir / "executable-3.sh", os.X_OK))
