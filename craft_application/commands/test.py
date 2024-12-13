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
"""Command to test a project."""

from __future__ import annotations

import argparse
import pathlib
from textwrap import dedent

import craft_cli

from . import base

TEMP_FILE_NAME = ".craft-spread.yaml"


class TestCommand(base.AppCommand):
    """Command to run project tests.

    The test command invokes the spread command with a processed spread.yaml
    configuration file.
    """

    name = "test"
    help_msg = "Run project tests"
    overview = dedent(
        """
        Execute project tests using spread.
        """
    )
    common = True

    def run(self, parsed_args: argparse.Namespace) -> None:  # noqa: ARG002
        """Run the command."""
        craft_cli.emit.progress("Testing project.")

        dest = pathlib.Path(TEMP_FILE_NAME)
        try:
            self._services.testing.process_spread_yaml(dest)
            self._services.testing.run_spread(dest)
        finally:
            dest.unlink()
