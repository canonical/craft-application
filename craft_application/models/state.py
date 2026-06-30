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
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Models representing application states."""

from __future__ import annotations

import pathlib

from craft_application.models import CraftBaseModel


class PackedArtifact(CraftBaseModel):
    """A persisted packed artifact entry."""

    name: str | None = None
    path: pathlib.Path


class PackState(CraftBaseModel):
    """Information about the packaged artifacts."""

    artifacts: list[PackedArtifact]

    @property
    def artifact(self) -> pathlib.Path | None:
        """Compatibility view for the primary artifact."""
        for artifact in self.artifacts:
            if artifact.name is None:
                return artifact.path
        return None

    @property
    def resources(self) -> dict[str, pathlib.Path] | None:
        """Compatibility view for secondary artifacts from the legacy API."""
        resources = {
            artifact.name: artifact.path
            for artifact in self.artifacts
            if artifact.name is not None
        }
        return resources or None
