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

import os
import pathlib
import textwrap

import jinja2
import pytest
import pytest_check
from craft_application import errors, services


@pytest.fixture
def init_service(app_metadata, fake_services):
    _init_service = services.InitService(app_metadata, fake_services)
    _init_service.setup()
    return _init_service


@pytest.fixture
def mock_loader(mocker, tmp_path):
    """Mock the loader so it does not try to import `testcraft.templates`."""
    return mocker.patch(
        "craft_application.services.init.InitService._get_loader",
        return_value=jinja2.FileSystemLoader(tmp_path / "templates"),
    )


def test_get_context(init_service):
    context = init_service._get_context(name="my-project")

    assert context == {"name": "my-project"}


@pytest.mark.parametrize("create_dir", [True, False])
def test_create_project_dir(init_service, tmp_path, emitter, create_dir):
    project_dir = tmp_path / "my-project"
    if create_dir:
        project_dir.mkdir()

    init_service._create_project_dir(project_dir=project_dir)

    assert project_dir.is_dir()
    emitter.assert_debug(f"Creating project directory {str(project_dir)!r}.")


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


@pytest.mark.usefixtures("mock_loader")
@pytest.mark.parametrize("project_file", [None, "file.txt"])
def test_check_for_existing_files(init_service, tmp_path, project_file):
    """No-op if there are no overlapping files."""
    # create template
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "file.txt").touch()
    # create project with a different file
    project_dir = tmp_path / "project"
    if project_file:
        project_dir.mkdir()
        (project_dir / "other-file.txt").touch()

    init_service.check_for_existing_files(
        project_dir=project_dir, template_dir=template_dir
    )


@pytest.mark.usefixtures("mock_loader")
def test_check_for_existing_files_error(init_service, tmp_path):
    """Error if there are overlapping files."""
    expected_error = textwrap.dedent(
        f"""\
        Cannot initialise project in {str(tmp_path / 'project')!r} because it would overwrite existing files.
        Existing files are:
          - file.txt"""
    )
    # create template
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    (template_dir / "file.txt").touch()
    # create project with a different file
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "file.txt").touch()

    with pytest.raises(errors.InitError, match=expected_error):
        init_service.check_for_existing_files(
            project_dir=project_dir, template_dir=template_dir
        )


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


@pytest.mark.parametrize("filename", ["jinja-file.txt.j2", "nested/jinja-file.txt.j2"])
@pytest.mark.usefixtures("mock_loader")
def test_render_project_with_templates(filename, init_service, tmp_path):
    """Render template files."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    template_dir = tmp_path / "templates"
    (template_dir / filename).parent.mkdir(parents=True, exist_ok=True)
    (template_dir / filename).write_text("{{ name }}")

    environment = init_service._get_templates_environment(template_dir)
    init_service._render_project(
        environment=environment,
        project_dir=project_dir,
        template_dir=template_dir,
        context={"name": "my-project"},
    )

    assert (project_dir / filename[:-3]).read_text() == "my-project"


@pytest.mark.parametrize("filename", ["file.txt", "nested/file.txt"])
@pytest.mark.usefixtures("mock_loader")
def test_render_project_non_templates(filename, init_service, tmp_path):
    """Copy non-template files when rendering a project."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    template_dir = tmp_path / "templates"
    (template_dir / filename).parent.mkdir(parents=True, exist_ok=True)
    (template_dir / filename).write_text("test content")

    environment = init_service._get_templates_environment(template_dir)
    init_service._render_project(
        environment=environment,
        project_dir=project_dir,
        template_dir=template_dir,
        context={"name": "my-project"},
    )

    assert (project_dir / filename).read_text() == "test content"


@pytest.mark.usefixtures("mock_loader")
def test_render_project_executable(init_service, tmp_path):
    """Test that executable permissions are set on rendered files."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    for filename in ["file-1.sh.j2", "file-2.sh"]:
        (template_dir / filename).write_text("#!/bin/bash\necho 'Hello, world!'")
        (template_dir / filename).chmod(0o755)
    for filename in ["file-3.txt.j2", "file-4.txt"]:
        (template_dir / filename).write_text("template content")

    environment = init_service._get_templates_environment(template_dir)
    init_service._render_project(
        environment=environment,
        project_dir=project_dir,
        template_dir=template_dir,
        context={"name": "my-project"},
    )

    pytest_check.is_true(os.access(project_dir / "file-1.sh", os.X_OK))
    pytest_check.is_true(os.access(project_dir / "file-2.sh", os.X_OK))
    pytest_check.is_false(os.access(project_dir / "file-3.txt", os.X_OK))
    pytest_check.is_false(os.access(project_dir / "file-4.txt", os.X_OK))
