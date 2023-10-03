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

from typing import TYPE_CHECKING, Any

from craft_cli import BaseCommand, emit

if TYPE_CHECKING:  # pragma: no cover
    import argparse

    from craft_application import application
    from craft_application.services import service_factory


class AppCommand(BaseCommand):
    """Command for use with craft-application."""

    always_load_project: bool = False
    """The project is also loaded in non-managed mode."""

    def __init__(self, config: dict[str, Any] | None) -> None:
        if config is None:
            # This should only be the case when the command is not going to be run.
            # For example, when requesting help on the command.
            emit.trace("Not completing command configuration")
            return

        super().__init__(config)

        self._app: application.AppMetadata = config["app"]
        self._services: service_factory.ServiceFactory = config["services"]

    def run_managed(
        self,
        parsed_args: argparse.Namespace,  # noqa: ARG002 (the unused argument is for subclasses)
    ) -> bool:
        """Whether this command should run in managed mode.

        By default returns `False`. Subclasses can override this method to change this,
        including by inspecting the arguments in `parsed_args`.
        """
        return False

    def get_managed_cmd(
        self,
        parsed_args: argparse.Namespace,  # - Used by subclasses
    ) -> list[str]:
        """Get the command to run in managed mode.

        :param parsed_args: The parsed arguments used.
        :returns: A list of strings ready to be passed into a craft-providers executor.
        :raises: RuntimeError if this command is not supposed to run managed.

        Commands that have additional parameters to pass in managed mode should
        override this method to include those parameters.
        """
        if not self.run_managed(parsed_args):
            raise RuntimeError("Unmanaged commands should not be run in managed mode.")
        cmd_name = self._app.name
        verbosity = emit.get_mode().name.lower()
        return [cmd_name, f"--verbosity={verbosity}", self.name]
