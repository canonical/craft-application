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
"""Services for partitioncraft."""

import craft_application


def register_services() -> None:
    """Register Partitioncraft's services.

    This registers with the ServiceFactory all the services that partitioncraft
    adds or overrides.
    """
    craft_application.ServiceFactory.register(
        "package", "PackageService", module="partitioncraft.services.package"
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
