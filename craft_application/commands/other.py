# Copyright 2023 Canonical Ltd.
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
"""Miscellaneous commands in the 'Other' command group."""
from __future__ import annotations

from typing import TYPE_CHECKING

from craft_cli import CommandGroup, emit

from craft_application.commands import base

if TYPE_CHECKING:  # pragma: no cover
    import argparse


def get_other_command_group() -> CommandGroup:
    """Return the lifecycle related command group."""
    commands: list[type[base.AppCommand]] = [
        VersionCommand,
    ]

    return CommandGroup(
        "Other",
        commands,
    )


class VersionCommand(base.AppCommand):
    """Show the snapcraft version."""

    name = "version"
    help_msg = "Show the application version and exit"
    overview = "Show the application version and exit"
    common = True

    def run(
        self, parsed_args: argparse.Namespace  # noqa: ARG002 (Unused method argument)
    ) -> None:
        """Run the command."""
        emit.message(f"{self._app.name} {self._app.version}")
