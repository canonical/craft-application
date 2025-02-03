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
import subprocess
import sys
import textwrap

import pytest

from craft_application import errors
from craft_application.models.project import Project
from craft_application.services import InitService
from tests.conftest import RepositoryDefinition

# init operates in the current working directory
pytestmark = pytest.mark.usefixtures("new_dir")


@pytest.fixture
def init_service(fake_init_service_class, app_metadata, fake_services):
    _init_service = fake_init_service_class(app_metadata, fake_services)
    _init_service.setup()

    return _init_service


@pytest.fixture
def fake_empty_template_dir(tmp_path) -> pathlib.Path:
    empty_template_dir_path = pathlib.Path(tmp_path / "templates")
    empty_template_dir_path.mkdir(parents=True)
    return empty_template_dir_path


@pytest.fixture
def project_yaml_filename() -> str:
    return "testcraft.yaml"


def get_testcraft_yaml(*, version: str = "git") -> str:
    return textwrap.dedent(
        """
        # This file configures testcraft.

        # (Required)
        name: {{ name }}

        # (Required)
        # The source package version
        version: <<version_placeholder>>

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
        """.replace(
            "<<version_placeholder>>", version
        )
    )


@pytest.fixture
def template_dir_with_testcraft_yaml_j2(
    fake_empty_template_dir: pathlib.Path,
    project_yaml_filename: str,
) -> pathlib.Path:
    """Creates the same testcraft.yaml file in the top-level and nested directories.

    Normally a project would only have one testcraft.yaml file, but two are created for testing.
    """
    template_text = get_testcraft_yaml()
    top_level_template = fake_empty_template_dir / f"{project_yaml_filename}.j2"
    top_level_template.write_text(template_text)
    nested_template = fake_empty_template_dir / "nested" / f"{project_yaml_filename}.j2"
    nested_template.parent.mkdir()
    nested_template.write_text(template_text)

    return fake_empty_template_dir


@pytest.fixture
def template_dir_with_versioned_testcraft_yaml_j2(
    fake_empty_template_dir: pathlib.Path,
    project_yaml_filename: str,
) -> pathlib.Path:
    """Creates the testcraft.yaml with {{ version }} marker."""
    template_text = get_testcraft_yaml(version="{{ version }}")
    top_level_template = fake_empty_template_dir / f"{project_yaml_filename}.j2"
    top_level_template.write_text(template_text)

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
def template_dir_with_executables(
    fake_empty_template_dir: pathlib.Path,
) -> pathlib.Path:
    """Create executable templated and non-templated files."""
    for filename in [
        "file.sh",
        "nested/file.sh",
        "template.sh.j2",
        "nested/template.sh.j2",
    ]:
        filepath = fake_empty_template_dir / filename
        filepath.parent.mkdir(exist_ok=True)
        with filepath.open("wt", encoding="utf8") as file:
            file.write("#!/bin/bash\necho 'Hello, world!'")
        filepath.chmod(0o755)

    return fake_empty_template_dir


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
    fake_empty_template_dir: pathlib.Path,
    emitter,
    check,
):
    """Initialise a project with an empty templates directory."""
    init_service.initialise_project(
        project_dir=fake_empty_project_dir,
        project_name="fake-project-dir",
        template_dir=fake_empty_template_dir,
    )

    with check:
        assert emitter.assert_progress("Rendered project.")
    with check:
        assert not list(
            fake_empty_project_dir.iterdir()
        ), "Project dir should be initialised empty"


def test_init_works_with_simple_template(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    template_dir_with_testcraft_yaml_j2: pathlib.Path,
    project_yaml_filename: str,
    emitter,
    check,
):
    """Initialise a project with a simple project template."""
    init_service.initialise_project(
        project_dir=fake_empty_project_dir,
        project_name="fake-project-dir",
        template_dir=template_dir_with_testcraft_yaml_j2,
    )

    with check:
        assert emitter.assert_progress("Rendered project.")

    project_yaml_paths = [
        fake_empty_project_dir / project_yaml_filename,
        fake_empty_project_dir / "nested" / project_yaml_filename,
    ]

    for project_yaml_path in project_yaml_paths:
        with check:
            assert (
                project_yaml_path.exists()
            ), "Project should be initialised with template"
            project = Project.from_yaml_file(project_yaml_path)
            assert project.name == fake_empty_project_dir.name


def test_init_works_with_single_template_and_custom_name(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    template_dir_with_testcraft_yaml_j2: pathlib.Path,
    project_yaml_filename: str,
    emitter,
    check,
):
    """Initialise a project with a single template file and custom name."""
    name = "some-other-test-project"
    init_service.initialise_project(
        project_dir=fake_empty_project_dir,
        project_name=name,
        template_dir=template_dir_with_testcraft_yaml_j2,
    )

    with check:
        assert emitter.assert_progress("Rendered project.")

    project_yaml_path = pathlib.Path(fake_empty_project_dir, project_yaml_filename)

    with check:
        assert project_yaml_path.exists(), "Project should be initialised with template"
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


def test_init_works_with_non_jinja2_templates(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    template_dir_with_multiple_non_ninja_files: pathlib.Path,
    emitter,
    check,
):
    init_service.initialise_project(
        project_dir=fake_empty_project_dir,
        project_name="fake-project-dir",
        template_dir=template_dir_with_multiple_non_ninja_files,
    )

    with check:
        assert emitter.assert_progress("Rendered project.")

    check_file_existence_and_content(
        check, fake_empty_project_dir / "file1.txt", "Content of file1.txt"
    )
    check_file_existence_and_content(
        check,
        fake_empty_project_dir / "nested" / "file2.txt",
        "Content of the nested file",
    )


def test_init_does_not_follow_symlinks_but_copies_them_as_is(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    template_dir_with_symlinks: pathlib.Path,
    project_yaml_filename: str,
    check,
):
    init_service.initialise_project(
        project_dir=fake_empty_project_dir,
        project_name="fake-project-dir",
        template_dir=template_dir_with_symlinks,
    )

    project = Project.from_yaml_file(fake_empty_project_dir / project_yaml_filename)
    with check:
        assert project.name == fake_empty_project_dir.name
    with check:
        assert (
            fake_empty_project_dir / "py3_symlink"
        ).is_symlink(), "Symlink should be left intact."


def test_init_copies_executables(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    template_dir_with_executables: pathlib.Path,
    check,
):
    """Executability of template files should be preserved."""
    init_service.initialise_project(
        project_dir=fake_empty_project_dir,
        project_name="fake-project-dir",
        template_dir=template_dir_with_executables,
    )

    for filename in ["file.sh", "nested/file.sh", "template.sh", "nested/template.sh"]:
        with check:
            assert (
                subprocess.check_output(
                    [str(fake_empty_project_dir / filename)], text=True
                )
                == "Hello, world!\n"
            )


def test_init_does_not_fail_on_non_empty_dir(
    init_service: InitService,
    non_empty_project_dir: pathlib.Path,
    template_dir_with_testcraft_yaml_j2: pathlib.Path,
    project_yaml_filename: str,
    emitter,
    check,
):
    init_service.initialise_project(
        project_dir=non_empty_project_dir,
        project_name="fake-non-empty-project-dir",
        template_dir=template_dir_with_testcraft_yaml_j2,
    )

    with check:
        assert emitter.assert_progress("Rendered project.")

    project_yaml_path = non_empty_project_dir / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialised with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == non_empty_project_dir.name


def test_init_does_not_override_existing_craft_yaml(
    init_service: InitService,
    non_empty_project_dir: pathlib.Path,
    template_dir_with_testcraft_yaml_j2,
    project_yaml_filename: str,
    fake_project: Project,
    emitter,
    check,
):
    fake_project.to_yaml_file(non_empty_project_dir / project_yaml_filename)

    init_service.initialise_project(
        project_dir=non_empty_project_dir,
        project_name="fake-project-dir",
        template_dir=template_dir_with_testcraft_yaml_j2,
    )

    with check:
        assert emitter.assert_progress("Rendered project.")

    project_yaml_path = non_empty_project_dir / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialised with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == fake_project.name


def test_init_with_different_name_and_directory(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    template_dir_with_testcraft_yaml_j2: pathlib.Path,
    project_yaml_filename: str,
    emitter,
    check,
):
    name = "some-custom-project"

    init_service.initialise_project(
        project_dir=fake_empty_project_dir,
        project_name=name,
        template_dir=template_dir_with_testcraft_yaml_j2,
    )

    with check:
        assert emitter.assert_progress("Rendered project.")

    project_yaml_path = fake_empty_project_dir / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialised with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == name


def test_init_with_default_arguments_uses_current_directory(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    template_dir_with_testcraft_yaml_j2: pathlib.Path,
    project_yaml_filename: str,
    emitter,
    check,
):
    expected_project_name = fake_empty_project_dir.name

    init_service.initialise_project(
        project_dir=fake_empty_project_dir,
        project_name="fake-project-dir",
        template_dir=template_dir_with_testcraft_yaml_j2,
    )

    with check:
        assert emitter.assert_progress("Rendered project.")

    project_yaml_path = fake_empty_project_dir / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialised with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == expected_project_name


def test_check_for_existing_files(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    template_dir_with_testcraft_yaml_j2: pathlib.Path,
):
    """No-op if there are no overlapping files."""
    init_service.check_for_existing_files(
        project_dir=fake_empty_project_dir,
        template_dir=template_dir_with_testcraft_yaml_j2,
    )


def test_check_for_existing_files_error(
    init_service: InitService,
    fake_empty_project_dir: pathlib.Path,
    template_dir_with_testcraft_yaml_j2: pathlib.Path,
):
    """No-op if there are no overlapping files."""
    expected_error = textwrap.dedent(
        f"""\
        Cannot initialise project in {str(fake_empty_project_dir)!r} because it would overwrite existing files.
        Existing files are:
          - nested/testcraft.yaml
          - testcraft.yaml"""
    )
    (fake_empty_project_dir / "testcraft.yaml").touch()
    (fake_empty_project_dir / "nested").mkdir()
    (fake_empty_project_dir / "nested" / "testcraft.yaml").touch()

    with pytest.raises(errors.InitError, match=expected_error):
        init_service.check_for_existing_files(
            project_dir=fake_empty_project_dir,
            template_dir=template_dir_with_testcraft_yaml_j2,
        )


def test_init_service_with_version_without_git_repository(
    init_service: InitService,
    empty_working_directory: pathlib.Path,
    template_dir_with_versioned_testcraft_yaml_j2: pathlib.Path,
    project_yaml_filename: str,
    check,
) -> None:
    project_path = empty_working_directory
    init_service.initialise_project(
        project_dir=project_path,
        project_name=project_path.name,
        template_dir=template_dir_with_versioned_testcraft_yaml_j2,
    )
    project_yaml_path = project_path / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialised with template"
    project = Project.from_yaml_file(project_yaml_path)
    assert project.version == init_service.default_version


def test_init_service_with_version_based_on_commit(
    init_service: InitService,
    repository_with_commit: RepositoryDefinition,
    template_dir_with_versioned_testcraft_yaml_j2: pathlib.Path,
    project_yaml_filename: str,
    check,
) -> None:
    project_path = repository_with_commit.repository_path
    init_service.initialise_project(
        project_dir=project_path,
        project_name=project_path.name,
        template_dir=template_dir_with_versioned_testcraft_yaml_j2,
    )
    project_yaml_path = project_path / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialised with template"
    project = Project.from_yaml_file(project_yaml_path)
    assert project.version == repository_with_commit.short_commit


def test_init_service_with_version_based_on_tag(
    init_service: InitService,
    repository_with_annotated_tag: RepositoryDefinition,
    template_dir_with_versioned_testcraft_yaml_j2: pathlib.Path,
    project_yaml_filename: str,
    check,
) -> None:
    project_path = repository_with_annotated_tag.repository_path
    init_service.initialise_project(
        project_dir=project_path,
        project_name=project_path.name,
        template_dir=template_dir_with_versioned_testcraft_yaml_j2,
    )
    project_yaml_path = project_path / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialised with template"
    project = Project.from_yaml_file(project_yaml_path)
    assert project.version == repository_with_annotated_tag.tag
