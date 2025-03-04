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
"""Main CLI for partitioncraft."""

from typing import Any

import craft_cli

import craft_application
from partitioncraft.application import PARTITIONCRAFT, Partitioncraft


def create_app() -> craft_application.Application:
    """Create the application.

    This is used both for running the app and for generating shell completion.
    This function is where the app should be configured before running it.
    """
    craft_application.ServiceFactory.register(
        "package", "PackageService", module="testcraft.services.package"
    )
    craft_application.ServiceFactory.register(
        "project",
        "PartitioncraftProjectService",
        module="partitioncraft.services.project",
    )
    craft_application.ServiceFactory.register(
        "provider",
        "PartitioncraftProviderService",
        module="partitioncraft.services.provider",
    )
    services = craft_application.ServiceFactory(app=PARTITIONCRAFT)

    return Partitioncraft(PARTITIONCRAFT, services=services)


def get_completion_data() -> tuple[craft_cli.Dispatcher, dict[str, Any]]:
    """Get the app info for use with craft-cli's completion module."""
    app = create_app()

    return app._create_dispatcher(), app.app_config  # noqa: SLF001
