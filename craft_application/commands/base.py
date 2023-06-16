#  This file is part of craft-application.
#
#  Copyright 2023 Canonical Ltd.
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
from __future__ import annotations

import argparse
from typing import Any

from craft_cli import BaseCommand, emit

from craft_application import app


class AppCommand(BaseCommand):
    """Command for use with craft-application."""

    run_managed: bool = False
    """Whether this command should run in managed mode."""

    def __init__(self, config: dict[str, Any]) -> None:
        super().__init__(config)
        self._app: app.AppMetadata = config["app"]

    def get_managed_cmd(self, parsed_args: argparse.Namespace) -> list[str]:
        """Get the command to run in managed mode.

        :param parsed_args: The parsed arguments used.
        :returns: A list of strings ready to be passed into a craft-providers executor.
        :raises: RuntimeError if this command is not supposed to run managed.

        Commands that have additional parameters to pass in managed mode should
        override this method to include those parameters.
        """
        if not self.run_managed:
            raise RuntimeError("Unmanaged commands should not be run in managed mode.")
        cmd_name = self._app.name
        verbosity = emit.get_mode().name.lower()
        return [cmd_name, f"--verbosity={verbosity}", self.name]
