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
"""Main Witchcraft app."""

import craft_application
from craft_application.application import Application
from typing_extensions import override

from .models import Project

WITCHCRAFT = craft_application.AppMetadata(
    name="witchcraft",
    summary="A craft for testing craft-application with weird settings",
    artifact_type="cauldron",
    docs_url="https://canonical-craft-application.readthedocs-hosted.com",
    source_ignore_patterns=["*.witchcraft", "witchcraft.yaml"],
    project_variables=["version"],
    mandatory_adoptable_fields=["version"],
    always_repack=False,
    check_supported_base=True,
    enable_for_grammar=True,
    ProjectClass=Project,
)


class Witchcraft(Application):
    """Witchcraft application definition."""

    @override
    def _enable_craft_parts_features(self) -> None:
        from craft_parts.features import Features  # noqa: PLC0415

        # enable the craft-parts Features that we use here, right before
        # loading the project and validating its parts.
        Features(enable_overlay=True)
