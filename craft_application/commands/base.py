#  This file is part of craft-application.
#
# Copyright 2023 Canonical Ltd.
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
"""Base command for craft-application commands."""
import argparse
import sys
from typing import List, cast

from craft_cli import BaseCommand, emit


class AppCommand(BaseCommand):
    """Command for use with craft-application."""

    is_managed: bool = False
    """Whether this command should run in managed mode."""

    def get_managed_cmd(self, parsed_args: argparse.Namespace) -> List[str]:
        """Get the command to run in managed mode.

        :param parsed_args: The parsed arguments used.
        :returns: A pre-made command ready to run in managed mode.
        :raises: RuntimeError if this command is not supposed to run managed.
        """
        if not self.is_managed:
            raise RuntimeError("Unmanaged commands should not be run managed.")
        cmd_name = sys.argv[0]
        if self.config is not None and "name" in self.config:
            cmd_name = cast(str, self.config["name"])
        verbosity = emit.get_mode().name.lower()
        cmd = [cmd_name, f"--verbosity={verbosity}", cast(str, self.name)]

        if getattr(parsed_args, "shell", False):
            cmd.append("--shell")
        if getattr(parsed_args, "shell_after", False):
            cmd.append("--shell-after")

        return cmd
