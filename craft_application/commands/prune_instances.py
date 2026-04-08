# Copyright 2026 Canonical Ltd.
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
"""Provider-related commands."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

from . import base

if TYPE_CHECKING:  # pragma: no cover
    import argparse


class PruneInstancesCommand(base.AppCommand):
    """Prune instances for the active provider."""

    name = "prune-instances"
    help_msg = "Prune instances for the active provider"
    overview = textwrap.dedent(
        """
        Prune instances for the active provider.
        """
    )

    def _fill_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--all-providers",
            action="store_true",
            help="Prune instances from all providers",
        )
        parser.add_argument(
            "--provider",
            help="Prune for a specific provider",
        )
        parser.add_argument(
            "--include-templates",
            action="store_true",
            help="Prune base instances (templates)",
        )

    def run(self, parsed_args: argparse.Namespace) -> None:
        """Run the prune-instances command."""
        self._services.provider.prune_instances(
            all_providers=parsed_args.all_providers,
            provider_name=parsed_args.provider,
            include_templates=parsed_args.include_templates,
        )
