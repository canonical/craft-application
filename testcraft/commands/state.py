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
"""Command to exercise the state service."""

from __future__ import annotations

from textwrap import dedent
from typing import TYPE_CHECKING

import craft_cli
from craft_application import util
from craft_application.commands import base
from overrides import override

if TYPE_CHECKING:
    import argparse


class StateCommand(base.AppCommand):
    """Command to exercise the state service."""

    name = "state"
    help_msg = "Get and set values in the state service."
    overview = dedent(
        """
        Get and set values in the state service in the inner and outer instances.
        """
    )

    @override
    def needs_project(
        self,
        parsed_args: argparse.Namespace,  # noqa: ARG002 (unused arg)
    ) -> bool:
        return True

    @override
    def run(self, parsed_args: argparse.Namespace) -> int | None:
        """Run the command.

        This command exercises:
        - Inner instance reading a value set in the outer instance.
        - Outer instance reading values set in all inner instances.
        """
        if util.is_managed_mode():
            build_planner = self._services.get("build_plan")
            config = self._services.get("config")
            platform = getattr(parsed_args, "platform", None) or config.get("platform")
            if platform:
                build_planner.set_platforms(platform)

            craft_cli.emit.debug("Accessing state from inner instance.")
            state_service = self._services.get("state")

            # set a value in the inner instance
            platform = build_planner.plan()[0].platform
            state_service.set("inner", platform, value=f"test-{platform}")

            # read a value from the outer instance
            value = state_service.get("outer")
            craft_cli.emit.message(f"Got value set by outer instance: {value}")

        else:
            craft_cli.emit.debug("Accessing state from outer instance.")
            state_service = self._services.get("state")

            # set a value in the outer instance
            state_service.set("outer", value="test-value")

            provider = self._services.get("provider")
            for build in self._services.get("build_plan").plan():
                provider.run_managed(build_info=build, enable_fetch_service=False)

            # read values from the inner instances
            for build in self._services.get("build_plan").plan():
                value = state_service.get("inner", build.platform)
                craft_cli.emit.message(f"Got value set by inner instance: {value}")
