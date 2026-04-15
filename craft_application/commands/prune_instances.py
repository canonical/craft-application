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
    help_msg = "Prune instances for the selected provider or all providers"
    overview = textwrap.dedent(
        """
        Prune instances using the standard provider-selection logic.
        Use --provider to prune instances for a specific provider, or
        --all-providers to prune instances from all providers.
        """
    )

    def _fill_parser(self, parser: argparse.ArgumentParser) -> None:
        provider_group = parser.add_mutually_exclusive_group()
        provider_group.add_argument(
            "--all-providers",
            action="store_true",
            help="Prune instances from all providers",
        )
        provider_group.add_argument(
            "--provider",
            help="Prune instances for a specific provider; omit to use the standard provider-selection logic",
        )

    def run(self, parsed_args: argparse.Namespace) -> None:
        """Run the prune-instances command."""
        self._services.provider.prune_instances(
            all_providers=parsed_args.all_providers,
            provider_name=parsed_args.provider,
            prune_templates=parsed_args.prune_templates,
        )
