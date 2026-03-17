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
"""Application implementation for partitioncraft."""

import craft_application
import craft_cli
import craft_parts
from typing_extensions import override

PARTITIONCRAFT = craft_application.AppMetadata(
    name="partitioncraft",
    summary="A craft for testing partitions in craft-application.",
    docs_url="https://canonical-craft-application.readthedocs-hosted.com",
    source_ignore_patterns=["*.partitioncraft"],
    project_variables=["version"],
    mandatory_adoptable_fields=["version"],
)


class Partitioncraft(craft_application.Application):
    """Partitioncraft."""

    @override
    def _enable_craft_parts_features(self) -> None:
        craft_cli.emit.debug("Enabling partitions")
        craft_parts.Features(enable_partitions=True)
