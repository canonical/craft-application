# This file is part of craft_application.
#
# Copyright 2025 Canonical Ltd.
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
"""Partitioncraft provider service.

This is only because we're doing weird things in partitioncraft. An app with partitions
probably will not require its own ProviderService.
"""

import contextlib
import pathlib
from collections.abc import Callable, Generator

import craft_platforms
import craft_providers
from craft_application.services import provider
from craft_providers.actions.snap_installer import Snap


class PartitioncraftProviderService(provider.ProviderService):
    """Provider service for Partitioncraft."""

    def setup(self) -> None:
        """Set up partitioncraft."""
        # Replace "partitoncraft" with the testcraft snap since we're packaged there.
        self.snaps = [Snap(name="testcraft", channel=None, classic=True)]

    @contextlib.contextmanager
    def instance(
        self,
        build_info: craft_platforms.BuildInfo,
        *,
        work_dir: pathlib.Path,
        allow_unstable: bool = True,
        clean_existing: bool = False,
        project_name: str | None = None,
        prepare_instance: Callable[[craft_providers.Executor], None] | None = None,
        use_base_instance: bool = True,
        **kwargs: bool | str | None,
    ) -> Generator[craft_providers.Executor, None, None]:
        """Get a partitioncraft-specific provider instance."""
        # Need to create a partitioncraft alias so we can run "partitioncraft".
        with super().instance(
            build_info,
            work_dir=work_dir,
            allow_unstable=allow_unstable,
            clean_existing=clean_existing,
            project_name=project_name,
            prepare_instance=prepare_instance,
            use_base_instance=use_base_instance,
            **kwargs,
        ) as instance:
            instance.execute_run(
                ["snap", "alias", "testcraft.partitioncraft", "partitioncraft"]
            )
            yield instance
