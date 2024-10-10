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
"""Command to initialise a project."""

from __future__ import annotations

import argparse
import os
import pathlib
import shutil
from textwrap import dedent
from typing import Any, cast

from craft_cli import emit
from jinja2 import (
    Environment,
    PackageLoader,
    StrictUndefined,
)

from craft_application.errors import PathInvalidError
from craft_application.util import make_executable

from . import base


class InitCommand(base.AppCommand):
    """Command to create initial project files."""

    name = "init"
    help_msg = "Create an initial project filetree"
    overview = dedent(
        """
        Command creates an initial project filetree.

        1. No positional arguments provided
        Initialize project in current working directory.

        2. One positional argument (<project_dir>) provided
        Initialize project in the <project_dir> directory.
        """
    )
    common = True

    def fill_parser(self, parser: argparse.ArgumentParser) -> None:
        """Specify command's specific parameters."""
        parser.add_argument(
            "project_dir",
            type=pathlib.Path,
            nargs="?",
            default=None,
            help=(
                "Path to initialize project in; defaults to <name> or current working directory."
            ),
        )
        parser.add_argument(
            "--name",
            type=str,
            default=None,
            help="The name of project; defaults to the current working directory name",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Initialise even if the directory is not empty (will not overwrite files)",
        )

    def run(self, parsed_args: argparse.Namespace) -> None:
        """Run the command."""
        project_dir = self._get_project_dir(parsed_args)
        name = self._get_name(parsed_args)
        context = self._get_context(parsed_args)
        template_dir = self._get_template_dir(parsed_args)
        environment = self._get_templates_environment(template_dir)
        executable_files = self._get_executable_files(parsed_args)

        self._create_project_dir(
            project_dir=project_dir, name=name, force=parsed_args.force
        )
        self._render_project(
            environment,
            project_dir,
            template_dir,
            context,
            executable_files,
        )

    def _copy_template_file(
        self,
        template_name: str,
        template_dir: pathlib.Path,
        project_dir: pathlib.Path,
    ) -> None:
        """Copy the non-ninja template from template_dir to project_dir.

        If the file already exists in the projects copying is skipped.

        :param project_dir: The directory to render the files into.
        :param template_dir: The directory where templates are stored.
        :param template_name: Name of the template to copy.
        """
        emit.debug(f"Copying file {template_name} to {project_dir}")
        template_file = template_dir / template_name
        destination_file = project_dir / template_name
        if destination_file.exists():
            emit.trace(f"Skipping file {template_name} as it is already present")
            return
        destination_file.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(template_file, destination_file, follow_symlinks=False)

    def _render_project(
        self,
        environment: Environment,
        project_dir: pathlib.Path,
        template_dir: pathlib.Path,
        context: dict[str, Any],
        executable_files: list[str],
    ) -> None:
        """Render files for a project from a template.

        :param environment: The Jinja environment to use.
        :param project_dir: The directory to render the files into.
        :param template_dir: The directory where templates are stored.
        :param context: The context to render the templates with.
        :param executable_files: The list of files that should be executable.
        """
        for template_name in environment.list_templates():
            if not template_name.endswith(".j2"):
                self._copy_template_file(template_name, template_dir, project_dir)
                continue
            template = environment.get_template(template_name)

            # trim off `.j2`
            rendered_template_name = pathlib.Path(template_name).stem
            emit.debug(f"Rendering {template_name} to {rendered_template_name}")

            path = project_dir / rendered_template_name
            if path.exists():
                emit.trace(f"Skipping file {template_name} as it is already present")
                continue
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("wt", encoding="utf8") as file:
                out = template.render(context)
                file.write(out)
                if rendered_template_name in executable_files and os.name == "posix":
                    make_executable(file)
                    emit.debug("  made executable")
        emit.message("Successfully initialised project.")

    def _get_template_dir(
        self,
        parsed_args: argparse.Namespace,  # noqa: ARG002 (unused-method-argument)
    ) -> pathlib.Path:
        """Return the path to the template directory."""
        return pathlib.Path("templates")

    def _get_executable_files(
        self,
        parsed_args: argparse.Namespace,  # noqa: ARG002 (unused-method-argument)
    ) -> list[str]:
        """Return the list of files that should be executable."""
        return []

    def _get_context(self, parsed_args: argparse.Namespace) -> dict[str, Any]:
        """Get context to render templates with.

        :returns: A dict of context variables.
        """
        name = self._get_name(parsed_args)
        emit.debug(f"Set project name to '{name}'")

        return {"name": name}

    def _get_project_dir(self, parsed_args: argparse.Namespace) -> pathlib.Path:
        """Get project dir where project should be initialized.

        It applies rules in the following order:
        - if <project_dir> is specified explicitly, it returns <project_dir>
        - if <project_dir> is undefined, it defaults to cwd
        """
        # if set explicitly, just return it
        if parsed_args.project_dir is not None:
            return pathlib.Path(parsed_args.project_dir)

        # If both args are undefined, default to current dir
        return pathlib.Path.cwd().resolve()

    def _get_name(self, parsed_args: argparse.Namespace) -> str:
        """Get name of the package that is about to be initialized.

        Check if name is set explicitly or fallback to project_dir.
        """
        if parsed_args.name is not None:
            return cast(str, parsed_args.name)
        return self._get_project_dir(parsed_args).name

    def _create_project_dir(
        self,
        project_dir: pathlib.Path,
        *,
        name: str,
        force: bool,
    ) -> None:
        """Create the project path if it does not already exist."""
        if not project_dir.exists():
            project_dir.mkdir(parents=True)
        elif any(project_dir.iterdir()) and not force:
            raise PathInvalidError(
                message=f"{str(project_dir)!r} is not empty.",
                resolution="Use --force to initialise in a nonempty directory.",
            )
        emit.debug(f"Using project directory {str(project_dir)!r} for {name}")

    def _get_templates_environment(self, template_dir: pathlib.Path) -> Environment:
        """Create and return a Jinja environment to deal with the templates."""
        loader = PackageLoader(self._app.name, str(template_dir))
        return Environment(
            loader=loader,
            autoescape=False,  # noqa: S701 (jinja2-autoescape-false)
            keep_trailing_newline=True,  # they're not text files if they don't end in newline!
            optimized=False,  # optimization doesn't make sense for one-offs
            undefined=StrictUndefined,
        )  # fail on undefined
