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

import os
import pathlib
import sys
from typing import TYPE_CHECKING, Any

from craft_cli import emit
from jinja2 import (
    BaseLoader,
    Environment,
    FileSystemLoader,
    PackageLoader,
    StrictUndefined,
)

from craft_application.errors import PathInvalidError
from craft_application.util import make_executable

from . import base

if TYPE_CHECKING:  # pragma: no cover
    import argparse


class InitCommand(base.AppCommand):
    """Show the snapcraft version."""

    name = "init"
    help_msg = "Create an initial project filetree"
    overview = "Create an initial project filetree"
    common = True

    def fill_parser(self, parser: argparse.ArgumentParser) -> None:
        """Specify command's specific parameters."""
        parser.add_argument(
            "--name", help="The name of the project; defaults to the directory name"
        )
        parser.add_argument(
            "-p",
            "--project-dir",
            type=pathlib.Path,
            default=pathlib.Path.cwd(),
            help="Specify the project's directory (defaults to current)",
        )
        parser.add_argument(
            "-f",
            "--force",
            action="store_true",
            help="Initialise even if the directory is not empty (will not overwrite files)",
        )

    def run(self, parsed_args: argparse.Namespace) -> None:  # (unused-method-argument)
        """Run the command."""
        template_dir = self._get_template_dir(parsed_args)
        project_dir = parsed_args.project_dir.resolve()
        context = self._get_context(parsed_args)
        environment = self._get_templates_environment(template_dir)
        executable_files = self._get_executable_files(parsed_args)

        self._create_project_dir(project_dir=project_dir, force=parsed_args.force)
        self._render_project(environment, project_dir, context, executable_files)

    def _render_project(
        self,
        environment: Environment,
        project_dir: pathlib.Path,
        context: dict[str, Any],
        executable_files: list[str],
    ) -> None:
        """Render files for a project from a template.

        :param environment: The Jinja environment to use.
        :param project_dir: The directory to render the files into.
        :param context: The context to render the templates with.
        :param executable_files: The list of files that should be executable.
        """
        for template_name in environment.list_templates():
            if not template_name.endswith(".j2"):
                emit.trace(f"Skipping file {template_name}")
                continue
            template = environment.get_template(template_name)

            # trim off `.j2`
            rendered_template_name = template_name[:-3]
            emit.debug(f"Rendering {template_name} to {rendered_template_name}")

            path = project_dir / rendered_template_name
            if path.exists():
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
        name = parsed_args.name or parsed_args.project_dir.resolve().name
        emit.debug(f"Set project name to '{name}'")

        return {"name": name}

    def _create_project_dir(self, project_dir: pathlib.Path, *, force: bool) -> None:
        """Create the project path if it does not already exist."""
        if not project_dir.exists():
            project_dir.mkdir(parents=True)
        elif any(project_dir.iterdir()) and not force:
            raise PathInvalidError(
                message=f"{str(project_dir)!r} is not empty.",
                resolution="Use --force to initialise in a nonempty directory.",
            )
        emit.debug(f"Using project directory {str(project_dir)!r}")

    def _get_templates_environment(self, template_dir: pathlib.Path) -> Environment:
        """Create and return a Jinja environment to deal with the templates."""
        if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
            # Running as PyInstaller bundle. For more information:
            # https://pyinstaller.readthedocs.io/en/stable/runtime-information.html
            # In this scenario we need to load from the data location that is unpacked
            # into the temporary directory at runtime (sys._MEIPASS).
            package_dir = pathlib.Path(sys._MEIPASS)  # type: ignore[reportUnknownMemberType,reportAttributeAccessIssue]
            loader: BaseLoader = FileSystemLoader(package_dir / template_dir)
        else:
            loader = PackageLoader(self._app.name, str(template_dir))

        return Environment(
            loader=loader,
            autoescape=False,  # noqa: S701 (jinja2-autoescape-false)
            keep_trailing_newline=True,  # they're not text files if they don't end in newline!
            optimized=False,  # optimization doesn't make sense for one-offs
            undefined=StrictUndefined,
        )  # fail on undefined
