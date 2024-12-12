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
import pytest_mock
from craft_cli.pytest_plugin import RecordingEmitter

from craft_application import errors, services
from craft_application.git import GitRepo, short_commit_sha
from craft_application.models.constraints import MESSAGE_INVALID_NAME


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


def test_get_context(init_service, tmp_path: pathlib.Path):
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    context = init_service._get_context(name="my-project", project_dir=project_dir)

    assert context == {"name": "my-project", "version": init_service.default_version}


@pytest.fixture
def empty_git_repository(tmp_path: pathlib.Path) -> GitRepo:
    repository = tmp_path / "my-project-git"
    repository.mkdir()
    return GitRepo(repository)


@pytest.fixture
def git_repository_with_commit(tmp_path: pathlib.Path) -> tuple[GitRepo, str]:
    repository = tmp_path / "my-project-git"
    repository.mkdir()
    git_repo = GitRepo(repository)
    (repository / "some_file").touch()
    git_repo.add_all()
    commit_sha = git_repo.commit("feat: initialize repo")

    return git_repo, commit_sha


@pytest.fixture
def project_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    project_dir = tmp_path / "my-project"
    project_dir.mkdir()
    return project_dir


@pytest.fixture
def templates_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    template_dir = tmp_path / "templates"
    template_dir.mkdir()
    return template_dir


def test_get_context_of_empty_git_repository(
    init_service, empty_git_repository: GitRepo
):
    context = init_service._get_context(
        name="my-project",
        project_dir=empty_git_repository.path,
    )

    assert context == {"name": "my-project", "version": init_service.default_version}


def test_get_context_of_git_repository_with_commit(
    init_service,
    git_repository_with_commit: tuple[GitRepo, str],
    emitter: RecordingEmitter,
):
    git_repo, commit_sha = git_repository_with_commit
    expected_version = short_commit_sha(commit_sha)
    context = init_service._get_context(
        name="my-project",
        project_dir=git_repo.path,
    )
    assert context == {"name": "my-project", "version": expected_version}
    emitter.assert_debug(f"Discovered project version: {expected_version!r}")


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
        context={"name": "my-project", "version": init_service.default_version},
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
        context={"name": "my-project", "version": init_service.default_version},
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
        context={"name": "my-project", "version": init_service.default_version},
    )

    pytest_check.is_true(os.access(project_dir / "file-1.sh", os.X_OK))
    pytest_check.is_true(os.access(project_dir / "file-2.sh", os.X_OK))
    pytest_check.is_false(os.access(project_dir / "file-3.txt", os.X_OK))
    pytest_check.is_false(os.access(project_dir / "file-4.txt", os.X_OK))


def test_initialise_project(
    init_service: services.InitService,
    project_dir: pathlib.Path,
    templates_dir: pathlib.Path,
    mocker: pytest_mock.MockerFixture,
) -> None:
    project_name = "test-project"
    fake_env = {"templates": templates_dir}
    fake_context = {"name": project_name, "version": init_service.default_version}
    get_templates_mock = mocker.patch.object(
        init_service, "_get_templates_environment", return_value=fake_env
    )
    create_project_dir_mock = mocker.patch.object(
        init_service,
        "_create_project_dir",
    )
    get_context_mock = mocker.patch.object(
        init_service,
        "_get_context",
        return_value=fake_context,
    )
    render_project_mock = mocker.patch.object(
        init_service,
        "_render_project",
    )
    init_service.initialise_project(
        project_dir=project_dir,
        project_name=project_name,
        template_dir=templates_dir,
    )
    get_templates_mock.assert_called_once_with(templates_dir)
    create_project_dir_mock.assert_called_once_with(project_dir=project_dir)
    get_context_mock.assert_called_once_with(name=project_name, project_dir=project_dir)
    render_project_mock.assert_called_once_with(
        fake_env, project_dir, templates_dir, fake_context
    )


@pytest.mark.parametrize(
    "invalid_name", ["invalid--name", "-invalid-name", "invalid-name-", "0", "0-0", ""]
)
def test_validate_name_invalid(init_service, invalid_name):
    with pytest.raises(errors.InitError, match=MESSAGE_INVALID_NAME):
        init_service.validate_project_name(invalid_name)


@pytest.mark.parametrize("valid_name", ["valid-name", "a", "a-a", "aaa", "0a"])
def test_validate_name_valid(init_service, valid_name):
    obtained = init_service.validate_project_name(valid_name)
    assert obtained == valid_name


def test_valid_name_invalid_use_default(init_service):
    invalid_name = "invalid--name"
    init_service._default_name = "my-default-name"

    obtained = init_service.validate_project_name(invalid_name, use_default=True)
    assert obtained == "my-default-name"
