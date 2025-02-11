# This file is part of craft-application.
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
"""Build planning service."""

from __future__ import annotations

from collections.abc import Collection, Iterable
from typing import Any

import craft_platforms

from . import base


class BuildPlanService(base.AppService):
    """A service for generating and filtering build plans."""

    _build_plan: Collection[craft_platforms.BuildInfo]

    def setup(self) -> None:
        super().setup()
        self._build_plan = []

    def gen_exhaustive_build_plan(
        self, project_data: dict[str, Any]
    ) -> Iterable[craft_platforms.BuildInfo]:
        """Generate the exhaustive build plan with craft-platforms.

        :param project_data: The unprocessed project data retrieved from a YAML file.
        :returns: An iterable of BuildInfo objects that make the exhaustive build plan.
        """
        return craft_platforms.get_build_plan(
            app=self._app.name, project_data=project_data
        )

    def gen_build_plan(
        self,
        project_data: dict[str, Any],
        *,
        platforms: Collection[str] | None,
        build_for: Collection[str] | None,
        build_on: Collection[str] | None = (
            str(craft_platforms.DebianArchitecture.from_host()),
        ),
    ) -> Iterable[craft_platforms.BuildInfo]:
        """Generate a build plan based on the given platforms, build-fors and build-ons.

        :param platforms: A sequence of platform names to select.
        :param build_for: A sequence of build-for architecture names to select.
        :param build_on: A sequence of build-on architecture names to select.
        """
        if build_for is not None:
            build_for_archs = {
                craft_platforms.DebianArchitecture(arch) for arch in build_for
            }
        else:
            build_for_archs = None

        if build_on is not None:
            build_on_archs = {
                craft_platforms.DebianArchitecture(arch) for arch in build_on
            }
        else:
            build_on_archs = None

        for item in self.gen_exhaustive_build_plan(project_data):
            if platforms is not None and item.platform not in platforms:
                continue
            if build_for_archs is not None and item.build_for not in build_for_archs:
                continue
            if build_on_archs is not None and item.build_on not in build_on_archs:
                continue
            yield item
