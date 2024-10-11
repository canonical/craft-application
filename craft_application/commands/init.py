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
import pathlib
from textwrap import dedent
from typing import cast

from . import base


class InitCommand(base.AppCommand):
    """Command to create initial project files."""

    name = "init"
    help_msg = "Create an initial project filetree"
    overview = dedent(
        """
        Initialise a project.

        If <project-dir> is provided, initialise in that directory,
        otherwise initialise in the current working directory.
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
            help="Path to initialize project in; defaults to current working directory.",
        )
        parser.add_argument(
            "--name",
            type=str,
            default=None,
            help="The name of project; defaults to the name of <project_dir>",
        )

    def run(self, parsed_args: argparse.Namespace) -> None:
        """Run the command."""
        project_dir = self._get_project_dir(parsed_args)
        name = self._get_name(parsed_args)
        self._services.init.run(project_dir=project_dir, name=name)

    def _get_name(self, parsed_args: argparse.Namespace) -> str:
        """Get name of the package that is about to be initialized.

        Check if name is set explicitly or fallback to project_dir.
        """
        if parsed_args.name is not None:
            return cast(str, parsed_args.name)
        return self._get_project_dir(parsed_args).name

    @staticmethod
    def _get_project_dir(parsed_args: argparse.Namespace) -> pathlib.Path:
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
