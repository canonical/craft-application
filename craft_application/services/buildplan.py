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

from typing import TYPE_CHECKING, Any, Literal, final

import craft_platforms
from craft_cli import emit

from craft_application.errors import EmptyBuildPlanError

from . import base

if TYPE_CHECKING:
    from collections.abc import Collection, Iterable, Sequence


class BuildPlanService(base.AppService):
    """A service for generating and filtering build plans."""

    def setup(self) -> None:
        """Set up the build plan service."""
        super().setup()
        self.__platforms: list[str] = []
        self.__build_for: list[craft_platforms.DebianArchitecture | Literal["all"]] = []
        self.__plan: Sequence[craft_platforms.BuildInfo] | None = None

    def set_platforms(self, *platform: str) -> None:
        """Set the platforms for the build plan."""
        self.__platforms = list(platform)
        # Reset cached plan
        self.__plan = None

    def set_build_fors(
        self, *build_for: craft_platforms.DebianArchitecture | str
    ) -> None:
        """Set the build-for (target) platforms for the build plan."""
        self.__build_for = [
            "all" if target == "all" else craft_platforms.DebianArchitecture(target)
            for target in build_for
        ]
        # Reset cached plan
        self.__plan = None

    @final
    def plan(self) -> Sequence[craft_platforms.BuildInfo]:
        """Plan the current build."""
        if not self.__plan:
            self.__plan = self.create_build_plan(
                platforms=self.__platforms or None,
                build_for=self.__build_for or None,
                build_on=[craft_platforms.DebianArchitecture.from_host()],
            )
        if not self.__plan:
            raise EmptyBuildPlanError
        return self.__plan

    def _gen_exhaustive_build_plan(
        self, project_data: dict[str, Any]
    ) -> Iterable[craft_platforms.BuildInfo]:
        """Generate the exhaustive build plan with craft-platforms.

        :param project_data: The unprocessed project data retrieved from a YAML file.
        :returns: An iterable of BuildInfo objects that make the exhaustive build plan.
        """
        return craft_platforms.get_build_plan(
            app=self._app.name, project_data=project_data
        )

    def _filter_plan(
        self,
        /,
        exhaustive_build_plan: Iterable[craft_platforms.BuildInfo],
        *,
        platforms: Collection[str] | None,
        build_for: Collection[craft_platforms.DebianArchitecture | Literal["all"]]
        | None,
        build_on: Collection[craft_platforms.DebianArchitecture] | None,
    ) -> Iterable[craft_platforms.BuildInfo]:
        """Filter the build plan.

        This method filters the given build plan based on the provided filter values.
        An application may override this if in needs to filter the build plan in
        non-default ways. It exists to allow applications to only change the build plan
        filter and should only be used by :meth:`get_build_plan` except in testing.

        :param platforms: A collection of platform names to keep after filtering, or
            ``None`` to not filter on the platform name.
        :param build_for: A collection of target architectures to keep after filtering,
            or ``None`` to not filter on the build-for architecture.
        :param build_on: A collection of build-on architectures to keep after
            filtering, or ``None`` to not filter on the build-on architecture.
        :yields: Build info objects based on the given filter.
        """
        platforms_built: set[str] = set()

        for item in exhaustive_build_plan:
            if platforms is not None and item.platform not in platforms:
                continue
            if build_for is not None and item.build_for not in build_for:
                continue
            if build_on is not None and item.build_on not in build_on:
                continue
            if item.platform in platforms_built:  # Don't render duplicate build items.
                continue
            platforms_built.add(item.platform)
            yield item

    @final
    def create_build_plan(
        self,
        *,
        platforms: Collection[str] | None,
        build_for: Collection[str | craft_platforms.DebianArchitecture] | None,
        build_on: Collection[str | craft_platforms.DebianArchitecture] | None,
    ) -> Sequence[craft_platforms.BuildInfo]:
        """Generate a build plan based on the given platforms, build-fors and build-ons.

        :param platforms: A collection of platform names to select, or None to not
            filter on platform names
        :param build_for: A collection of build-for architecture names to select, or
            None to not filter on build-for architectures.
        :param build_on: A collection of build-on architecture names to select.
            Defaults to the current architecture.
        :returns: A build plan for the given
        """
        project_service = self._services.get("project")
        raw_project = project_service.get_raw()
        raw_project["platforms"] = project_service.get_platforms()

        if build_on:
            build_on_archs = [craft_platforms.DebianArchitecture(on) for on in build_on]
        else:
            build_on_archs = None

        if build_for:
            build_for_archs = [
                "all" if fr == "all" else craft_platforms.DebianArchitecture(fr)
                for fr in build_for
            ]
        else:
            build_for_archs = None

        plan = list(
            self._filter_plan(
                self._gen_exhaustive_build_plan(project_data=raw_project),
                platforms=platforms,
                build_for=build_for_archs,  # type: ignore[arg-type]  # Literal "all"
                build_on=build_on_archs,
            )
        )

        emit.debug(f"Build plan contains {len(plan)} build(s).")
        emit.trace(f"Build plan: {str(plan)}")

        return plan
