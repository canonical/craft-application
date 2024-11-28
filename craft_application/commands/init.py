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
import importlib.resources
import pathlib
from textwrap import dedent
from typing import cast

import craft_cli

from craft_application.util import humanize_list

from . import base


class InitCommand(base.AppCommand):
    """Command to create initial project files.

    The init command should always produce a working and ready-to-build project.
    """

    name = "init"
    help_msg = "Create an initial project filetree"
    overview = dedent(
        """
        Initialise a project.

        If '<project-dir>' is provided, initialise in that directory,
        otherwise initialise in the current working directory.

        If '--name <name>' is provided, the project will be named '<name>'.
        Otherwise, the project will be named after the directory it is initialised in.

        '--profile <profile>' is used to initialise the project for a specific use case.

        Init can work in an existing project directory. If there are any files in the
        directory that would be overwritten, then init command will fail.
        """
    )
    common = True

    default_profile = "simple"
    """The default profile to use when initialising a project."""

    def fill_parser(self, parser: argparse.ArgumentParser) -> None:
        """Specify command's specific parameters."""
        parser.add_argument(
            "project_dir",
            type=pathlib.Path,
            nargs="?",
            default=None,
            help="Path to initialise project in; defaults to current working directory.",
        )
        parser.add_argument(
            "--name",
            type=str,
            default=None,
            help="The name of project; defaults to the name of <project_dir>",
        )
        parser.add_argument(
            "--profile",
            type=str,
            choices=self.profiles,
            default=self.default_profile,
            help=(
                f"Use the specified project profile (default is {self.default_profile}, "
                f"choices are {humanize_list(self.profiles, 'and')})"
            ),
        )

    @property
    def parent_template_dir(self) -> pathlib.Path:
        """Return the path to the directory that contains all templates."""
        with importlib.resources.path(
            self._app.name, "templates"
        ) as _parent_template_dir:
            return _parent_template_dir

    @property
    def profiles(self) -> list[str]:
        """A list of profile names generated from template directories."""
        template_dirs = [
            path for path in self.parent_template_dir.iterdir() if path.is_dir()
        ]
        return sorted([template.name for template in template_dirs])

    def run(self, parsed_args: argparse.Namespace) -> None:
        """Run the command."""
        # If the user provided a "name" and it's not valid, the command fails.
        if parsed_args.name is not None:
            self._services.init.validate_project_name(parsed_args.name)

        # However, if the name comes from the directory, we don't fail and
        # instead fallback to its default.
        project_name = self._get_name(parsed_args)
        project_name = self._services.init.validate_project_name(
            project_name, use_default=True
        )

        project_dir = self._get_project_dir(parsed_args)
        template_dir = pathlib.Path(self.parent_template_dir / parsed_args.profile)

        craft_cli.emit.progress("Checking project directory.")
        self._services.init.check_for_existing_files(
            project_dir=project_dir, template_dir=template_dir
        )

        craft_cli.emit.progress("Initialising project.")
        self._services.init.initialise_project(
            project_dir=project_dir,
            project_name=project_name,
            template_dir=template_dir,
        )
        craft_cli.emit.message("Successfully initialised project.")

    def _get_name(self, parsed_args: argparse.Namespace) -> str:
        """Get name of the package that is about to be initialised.

        Check if name is set explicitly or fallback to project_dir.
        """
        if parsed_args.name is not None:
            return cast(str, parsed_args.name)
        return self._get_project_dir(parsed_args).name

    @staticmethod
    def _get_project_dir(parsed_args: argparse.Namespace) -> pathlib.Path:
        """Get project dir where project should be initialised.

        It applies rules in the following order:
        - if <project_dir> is specified explicitly, it returns <project_dir>
        - if <project_dir> is undefined, it defaults to cwd
        """
        # if set explicitly, just return it
        if parsed_args.project_dir is not None:
            return pathlib.Path(parsed_args.project_dir).expanduser().resolve()

        # If both args are undefined, default to current dir
        return pathlib.Path.cwd().resolve()
