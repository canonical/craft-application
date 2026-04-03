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
"""Witchcraft provider service."""

import contextlib
import pathlib
from collections.abc import Callable, Generator

import craft_platforms
import craft_providers
from craft_application.services import provider
from typing_extensions import override


class ProviderService(provider.ProviderService):
    """Provider service for witchcraft."""

    @override
    def _setup_snaps(self) -> None:
        """Inject Testcraft since there is no "witchcraft" snap."""
        super()._setup_snaps()
        self.enqueue_snap_injection("testcraft")

    @override
    @contextlib.contextmanager
    def instance(
        self,
        build_info: craft_platforms.BuildInfo,
        *,
        work_dir: pathlib.Path,
        allow_unstable: bool = True,
        clean_existing: bool = False,
        use_base_instance: bool = True,
        project_name: str | None = None,
        prepare_instance: Callable[[craft_providers.Executor], None] | None = None,
        **kwargs: bool | str | None,
    ) -> Generator[craft_providers.Executor, None, None]:
        """Inject the alias for Witchcraft to run in the managed instance."""
        with super().instance(
            build_info,
            work_dir=work_dir,
            allow_unstable=allow_unstable,
            clean_existing=clean_existing,
            use_base_instance=use_base_instance,
            project_name=project_name,
            prepare_instance=prepare_instance,
            **kwargs,
        ) as instance:
            instance.execute_run(
                ["snap", "alias", "testcraft.witchcraft", "witchcraft"]
            )
            yield instance
