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

"""Tests for init service."""

import pathlib
import sys
import textwrap

import pytest
from craft_application.models.project import Project
from craft_application.services import InitService
from jinja2 import FileSystemLoader

# init operates in the current working directory
pytestmark = pytest.mark.usefixtures("new_dir")


@pytest.fixture
def init_service(app_metadata, fake_services, mocker, tmp_path):
    _init_service = InitService(app_metadata, fake_services)
    _init_service.setup()

    mocker.patch.object(
        _init_service,
        "_get_loader",
        return_value=FileSystemLoader(tmp_path / "templates"),
    )

    return _init_service


@pytest.fixture
def fake_empty_template_dir(tmp_path) -> pathlib.Path:
    empty_template_dir_path = pathlib.Path(tmp_path / "templates")
    empty_template_dir_path.mkdir(parents=True)
    return empty_template_dir_path


@pytest.fixture
def project_yaml_filename() -> str:
    return "testcraft.yaml"


# TODO: test nested templates


@pytest.fixture
def template_dir_with_testcraft_yaml_j2(
    fake_empty_template_dir: pathlib.Path,
    project_yaml_filename: str,
) -> pathlib.Path:
    (fake_empty_template_dir / f"{project_yaml_filename}.j2").write_text(
        textwrap.dedent(
            """
        # This file configures testcraft.

        # (Required)
        name: {{ name }}

        # (Required)
        # The source package version
        version: git

        # (Required)
        # Version of the build base OS
        base: ubuntu@24.04

        # (Recommended)
        title: Testcraft Template Package

        # (Required)
        summary: A very short one-line summary of the package.

        # (Required)
        description: |
          A single sentence that says what the source is, concisely and memorably.

          A paragraph of one to three short sentences, that describe what the package does.

          A third paragraph that explains what need the package meets.

          Finally, a paragraph that describes whom the package is useful for.


        parts:
          {{ name }}:
            plugin: nil
            source: .
        platforms:
          amd64:
        """
        )
    )

    return fake_empty_template_dir


@pytest.fixture
def template_dir_with_multiple_non_ninja_files(
    fake_empty_template_dir: pathlib.Path,
) -> pathlib.Path:
    file_1 = fake_empty_template_dir / "file1.txt"
    file_1.write_text("Content of file1.txt")
    file_2 = fake_empty_template_dir / "nested" / "file2.txt"
    file_2.parent.mkdir()
    file_2.write_text("Content of the nested file")
    return fake_empty_template_dir


@pytest.fixture
def template_dir_with_symlinks(
    template_dir_with_testcraft_yaml_j2: pathlib.Path,
) -> pathlib.Path:
    symlink_to_python_executable = template_dir_with_testcraft_yaml_j2 / "py3_symlink"
    symlink_to_python_executable.symlink_to(sys.executable)
    return template_dir_with_testcraft_yaml_j2


@pytest.fixture
def fake_empty_project_dir(tmp_path) -> pathlib.Path:
    empty_project_dir_path = pathlib.Path(tmp_path / "fake-project-dir")
    empty_project_dir_path.mkdir()
    return empty_project_dir_path


@pytest.fixture
def non_empty_project_dir(tmp_path) -> pathlib.Path:
    non_empty_project_dir_path = pathlib.Path(tmp_path / "fake-non-empty-project-dir")
    non_empty_project_dir_path.mkdir()
    (non_empty_project_dir_path / "some_project_file").touch()
    return non_empty_project_dir_path


@pytest.mark.usefixtures("fake_empty_template_dir")
def test_init_works_with_empty_templates_dir(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    emitter,
    check,
):
    """Initialize a project with an empty templates directory."""
    init_service.run(project_dir=fake_empty_project_dir, name="fake-project-dir")

    with check:
        assert emitter.assert_message("Successfully initialised project.")
    with check:
        assert not list(
            fake_empty_project_dir.iterdir()
        ), "Project dir should be initialized empty"


@pytest.mark.usefixtures("template_dir_with_testcraft_yaml_j2")
def test_init_works_with_single_template_file(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    project_yaml_filename: str,
    emitter,
    check,
):
    """Initialize a project with a single template file."""
    init_service.run(project_dir=fake_empty_project_dir, name="fake-project-dir")

    with check:
        assert emitter.assert_message("Successfully initialised project.")

    project_yaml_path = fake_empty_project_dir / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialized with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == fake_empty_project_dir.name


@pytest.mark.usefixtures("template_dir_with_testcraft_yaml_j2")
def test_init_works_with_single_template_and_custom_name(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    project_yaml_filename: str,
    emitter,
    check,
):
    """Initialize a project with a single template file and custom name."""
    name = "some-other-test-project"
    init_service.run(project_dir=fake_empty_project_dir, name=name)

    with check:
        assert emitter.assert_message("Successfully initialised project.")

    project_yaml_path = pathlib.Path(fake_empty_project_dir, project_yaml_filename)

    with check:
        assert project_yaml_path.exists(), "Project should be initialized with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == name


def check_file_existence_and_content(
    check, file_path: pathlib.Path, content: str
) -> None:
    """Helper function to ensure a file exists and has the correct content."""
    with check:
        assert file_path.exists(), f"{file_path.name} should be created"

    with check:
        assert file_path.read_text() == content, f"{file_path.name} incorrect content"


@pytest.mark.usefixtures("template_dir_with_multiple_non_ninja_files")
def test_init_works_with_non_jinja2_templates(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    emitter,
    check,
):
    init_service.run(project_dir=fake_empty_project_dir, name="fake-project-dir")

    with check:
        assert emitter.assert_message("Successfully initialised project.")

    check_file_existence_and_content(
        check, fake_empty_project_dir / "file1.txt", "Content of file1.txt"
    )
    check_file_existence_and_content(
        check,
        fake_empty_project_dir / "nested" / "file2.txt",
        "Content of the nested file",
    )


@pytest.mark.usefixtures("template_dir_with_symlinks")
def test_init_does_not_follow_symlinks_but_copies_them_as_is(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    project_yaml_filename: str,
    check,
):
    init_service.run(project_dir=fake_empty_project_dir, name="fake-project-dir")

    project = Project.from_yaml_file(fake_empty_project_dir / project_yaml_filename)
    with check:
        assert project.name == fake_empty_project_dir.name
    with check:
        assert (
            fake_empty_project_dir / "py3_symlink"
        ).is_symlink(), "Symlink should be left intact."


@pytest.mark.usefixtures("template_dir_with_testcraft_yaml_j2")
def test_init_does_not_fail_on_non_empty_dir(
    init_service: InitService,
    non_empty_project_dir: pathlib.Path,
    project_yaml_filename: str,
    emitter,
    check,
):
    init_service.run(
        project_dir=non_empty_project_dir, name="fake-non-empty-project-dir"
    )

    with check:
        assert emitter.assert_message("Successfully initialised project.")

    project_yaml_path = non_empty_project_dir / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialized with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == non_empty_project_dir.name


@pytest.mark.usefixtures("template_dir_with_testcraft_yaml_j2")
def test_init_does_not_override_existing_craft_yaml(
    init_service: InitService,
    non_empty_project_dir: pathlib.Path,
    project_yaml_filename: str,
    fake_project: Project,
    emitter,
    check,
):
    fake_project.to_yaml_file(non_empty_project_dir / project_yaml_filename)

    init_service.run(project_dir=non_empty_project_dir, name="fake-project-dir")

    with check:
        assert emitter.assert_message("Successfully initialised project.")

    project_yaml_path = non_empty_project_dir / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialized with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == fake_project.name


@pytest.mark.usefixtures("template_dir_with_testcraft_yaml_j2")
def test_init_with_different_name_and_directory(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    project_yaml_filename: str,
    emitter,
    check,
):
    name = "some-custom-project"

    init_service.run(project_dir=fake_empty_project_dir, name=name)

    with check:
        assert emitter.assert_message("Successfully initialised project.")

    project_yaml_path = fake_empty_project_dir / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialized with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == name


@pytest.mark.usefixtures("template_dir_with_testcraft_yaml_j2")
def test_init_with_default_arguments_uses_current_directory(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    project_yaml_filename: str,
    emitter,
    check,
):
    expected_project_name = fake_empty_project_dir.name

    init_service.run(project_dir=fake_empty_project_dir, name="fake-project-dir")

    with check:
        assert emitter.assert_message("Successfully initialised project.")

    project_yaml_path = fake_empty_project_dir / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialized with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == expected_project_name
