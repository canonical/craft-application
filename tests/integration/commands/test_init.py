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
import sys
from pathlib import Path
from textwrap import dedent

import pytest
from craft_application.commands.init import (
    InitCommand,
)
from craft_application.models.project import Project
from jinja2 import Environment, FileSystemLoader, StrictUndefined, Undefined


@pytest.fixture
def fake_empty_template_dir(tmp_path) -> Path:
    empty_template_dir_path = Path(tmp_path / "fake_template_dir")
    empty_template_dir_path.mkdir()
    return empty_template_dir_path


@pytest.fixture
def project_yaml_filename() -> str:
    return "testcraft.yaml"


@pytest.fixture
def template_dir_with_testcraft_yaml_j2(
    fake_empty_template_dir: Path,
    project_yaml_filename: str,
) -> Path:
    (fake_empty_template_dir / f"{project_yaml_filename}.j2").write_text(
        dedent(
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
    fake_empty_template_dir: Path,
) -> Path:
    file_1 = fake_empty_template_dir / "file1.txt"
    file_1.write_text("Content of file1.txt")
    file_2 = fake_empty_template_dir / "nested" / "file2.txt"
    file_2.parent.mkdir()
    file_2.write_text("Content of the nested file")
    return fake_empty_template_dir


@pytest.fixture
def template_dir_with_symlinks(
    template_dir_with_testcraft_yaml_j2: Path,
) -> Path:
    symlink_to_python_executable = template_dir_with_testcraft_yaml_j2 / "py3_symlink"
    symlink_to_python_executable.symlink_to(sys.executable)
    return template_dir_with_testcraft_yaml_j2


@pytest.fixture
def fake_empty_project_dir(tmp_path, monkeypatch) -> Path:
    empty_project_dir_path = Path(tmp_path / "fake-project-dir")
    empty_project_dir_path.mkdir()
    monkeypatch.chdir(empty_project_dir_path)
    return empty_project_dir_path


@pytest.fixture
def non_empty_project_dir(tmp_path, monkeypatch) -> Path:
    non_empty_project_dir_path = Path(tmp_path / "fake-non-empty-project-dir")
    non_empty_project_dir_path.mkdir()
    (non_empty_project_dir_path / "some_project_file").touch()
    monkeypatch.chdir(non_empty_project_dir_path)
    return non_empty_project_dir_path


def get_jinja2_template_environment(
    fake_template_dir: Path,
    *,
    autoescape: bool = False,
    keep_trailing_newline: bool = True,
    optimized: bool = False,
    undefined: type[Undefined] = StrictUndefined,
) -> Environment:
    return Environment(
        loader=FileSystemLoader(fake_template_dir),
        autoescape=autoescape,  # noqa: S701 (jinja2-autoescape-false)
        keep_trailing_newline=keep_trailing_newline,
        optimized=optimized,
        undefined=undefined,
    )


def get_command_arguments(
    *,
    name: str | None = None,
    project_dir: Path | None = None,
) -> argparse.Namespace:
    return argparse.Namespace(
        project_dir=project_dir,
        name=name,
    )


@pytest.fixture
def init_command(app_metadata) -> InitCommand:
    return InitCommand({"app": app_metadata, "services": []})


def test_init_works_with_empty_templates_dir(
    init_command: InitCommand,
    fake_empty_project_dir: Path,
    fake_empty_template_dir,
    emitter,
    mocker,
    check,
):
    parsed_args = get_command_arguments()
    mocker.patch.object(
        init_command,
        "_get_templates_environment",
        return_value=get_jinja2_template_environment(fake_empty_template_dir),
    )
    init_command.run(parsed_args)

    with check:
        assert emitter.assert_message("Successfully initialised project.")
    with check:
        assert not list(
            fake_empty_project_dir.iterdir()
        ), "Project dir should be initialized empty"


def test_init_works_with_single_template_file(
    init_command: InitCommand,
    fake_empty_project_dir: Path,
    project_yaml_filename: str,
    template_dir_with_testcraft_yaml_j2: Path,
    emitter,
    mocker,
    check,
):
    parsed_args = get_command_arguments()
    mocker.patch.object(
        init_command,
        "_get_templates_environment",
        return_value=get_jinja2_template_environment(
            template_dir_with_testcraft_yaml_j2
        ),
    )
    init_command.run(parsed_args)

    with check:
        assert emitter.assert_message("Successfully initialised project.")

    project_yaml_path = fake_empty_project_dir / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialized with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == fake_empty_project_dir.name


def test_init_works_with_single_template_and_custom_name(
    init_command: InitCommand,
    fake_empty_project_dir: Path,
    project_yaml_filename: str,
    template_dir_with_testcraft_yaml_j2: Path,
    emitter,
    mocker,
    check,
):
    custom_name = "some-other-testproject"
    parsed_args = get_command_arguments(name=custom_name)
    mocker.patch.object(
        init_command,
        "_get_templates_environment",
        return_value=get_jinja2_template_environment(
            template_dir_with_testcraft_yaml_j2
        ),
    )
    init_command.run(parsed_args)

    with check:
        assert emitter.assert_message("Successfully initialised project.")

    project_yaml_path = Path(fake_empty_project_dir, project_yaml_filename)

    with check:
        assert project_yaml_path.exists(), "Project should be initialized with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == custom_name


def check_file_existence_and_content(
    check,
    file_path: Path,
    content: str,
) -> None:
    with check:
        assert file_path.exists(), f"{file_path.name} should be created"

    with check:
        assert file_path.read_text() == content, f"{file_path.name} incorrect content"


def test_init_works_with_non_jinja2_templates(
    init_command: InitCommand,
    fake_empty_project_dir: Path,
    template_dir_with_multiple_non_ninja_files: Path,
    emitter,
    mocker,
    check,
):
    parsed_args = get_command_arguments()

    mocker.patch.object(
        init_command,
        "_get_template_dir",
        return_value=template_dir_with_multiple_non_ninja_files,
    )

    mocker.patch.object(
        init_command,
        "_get_templates_environment",
        return_value=get_jinja2_template_environment(
            template_dir_with_multiple_non_ninja_files
        ),
    )
    init_command.run(parsed_args)

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


def test_init_does_not_follow_symlinks_but_copies_them_as_is(
    init_command: InitCommand,
    fake_empty_project_dir: Path,
    project_yaml_filename: str,
    template_dir_with_symlinks: Path,
    mocker,
    check,
):
    parsed_args = get_command_arguments()

    mocker.patch.object(
        init_command,
        "_get_template_dir",
        return_value=template_dir_with_symlinks,
    )

    mocker.patch.object(
        init_command,
        "_get_templates_environment",
        return_value=get_jinja2_template_environment(template_dir_with_symlinks),
    )
    init_command.run(parsed_args)

    project = Project.from_yaml_file(fake_empty_project_dir / project_yaml_filename)
    with check:
        assert project.name == fake_empty_project_dir.name
    with check:
        assert (
            fake_empty_project_dir / "py3_symlink"
        ).is_symlink(), "Symlink should be left intact."


def test_init_does_not_fail_on_non_empty_dir(
    init_command: InitCommand,
    non_empty_project_dir: Path,
    project_yaml_filename: str,
    template_dir_with_testcraft_yaml_j2: Path,
    mocker,
    emitter,
    check,
):
    parsed_args = get_command_arguments()

    mocker.patch.object(
        init_command,
        "_get_template_dir",
        return_value=template_dir_with_testcraft_yaml_j2,
    )

    mocker.patch.object(
        init_command,
        "_get_templates_environment",
        return_value=get_jinja2_template_environment(
            template_dir_with_testcraft_yaml_j2
        ),
    )
    init_command.run(parsed_args)

    with check:
        assert emitter.assert_message("Successfully initialised project.")

    project_yaml_path = non_empty_project_dir / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialized with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == non_empty_project_dir.name


def test_init_does_not_override_existing_craft_yaml(
    init_command: InitCommand,
    non_empty_project_dir: Path,
    project_yaml_filename: str,
    fake_project: Project,
    template_dir_with_testcraft_yaml_j2: Path,
    mocker,
    emitter,
    check,
):
    parsed_args = get_command_arguments(project_dir=non_empty_project_dir)
    fake_project.to_yaml_file(non_empty_project_dir / project_yaml_filename)

    mocker.patch.object(
        init_command,
        "_get_template_dir",
        return_value=template_dir_with_testcraft_yaml_j2,
    )

    mocker.patch.object(
        init_command,
        "_get_templates_environment",
        return_value=get_jinja2_template_environment(
            template_dir_with_testcraft_yaml_j2
        ),
    )
    init_command.run(parsed_args)

    with check:
        assert emitter.assert_message("Successfully initialised project.")

    project_yaml_path = non_empty_project_dir / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialized with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == fake_project.name


def test_init_with_different_name_and_directory(
    init_command: InitCommand,
    fake_empty_project_dir: Path,
    template_dir_with_testcraft_yaml_j2: Path,
    project_yaml_filename: str,
    mocker,
    emitter,
    check,
):
    custom_project_name = "some-custom-project"
    parsed_args = get_command_arguments(
        name=custom_project_name,
        project_dir=fake_empty_project_dir,
    )

    mocker.patch.object(
        init_command,
        "_get_template_dir",
        return_value=template_dir_with_testcraft_yaml_j2,
    )

    mocker.patch.object(
        init_command,
        "_get_templates_environment",
        return_value=get_jinja2_template_environment(
            template_dir_with_testcraft_yaml_j2
        ),
    )
    init_command.run(parsed_args)

    with check:
        assert emitter.assert_message("Successfully initialised project.")

    project_yaml_path = fake_empty_project_dir / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialized with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == custom_project_name


def test_init_with_default_arguments_uses_current_directory(
    init_command: InitCommand,
    fake_empty_project_dir: Path,
    template_dir_with_testcraft_yaml_j2: Path,
    project_yaml_filename: str,
    mocker,
    emitter,
    check,
):
    expected_project_name = fake_empty_project_dir.name
    parsed_args = get_command_arguments()

    mocker.patch.object(
        init_command,
        "_get_template_dir",
        return_value=template_dir_with_testcraft_yaml_j2,
    )

    mocker.patch.object(
        init_command,
        "_get_templates_environment",
        return_value=get_jinja2_template_environment(
            template_dir_with_testcraft_yaml_j2
        ),
    )

    init_command.run(parsed_args)

    with check:
        assert emitter.assert_message("Successfully initialised project.")

    project_yaml_path = fake_empty_project_dir / project_yaml_filename

    with check:
        assert project_yaml_path.exists(), "Project should be initialized with template"
    project = Project.from_yaml_file(project_yaml_path)
    with check:
        assert project.name == expected_project_name
