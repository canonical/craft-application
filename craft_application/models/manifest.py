# This file is part of craft-application.
#
# Copyright 2024 Canonical Ltd.
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
"""Models representing manifests for projects and fetch-service assets."""
from typing import Any, Literal

from pydantic import Field
from typing_extensions import override

from craft_application.models import CraftBaseModel


class Hashes(CraftBaseModel):
    """Digests identifying an artifact/asset."""

    sha1: str = Field(alias="SHA1")
    sha256: str = Field(alias="SHA256")


class ComponentID(CraftBaseModel):
    """Unique identifications for an artifact/asset."""

    hashes: Hashes


class BaseManifestModel(CraftBaseModel):
    """Common properties shared between project and fetch-service manifests."""

    component_name: str
    component_version: str
    component_description: str
    component_id: ComponentID
    architecture: str


class ProjectManifest(BaseManifestModel):
    """Model for the project-specific properties of the craft manifest."""

    license: str | None = None
    comment: str | None = None
    metadata_generator: Literal["Craft Application"] = "Craft Application"
    creation_timestamp: str

    @override
    def marshal(self) -> dict[str, str | list[str] | dict[str, Any]]:
        """Overridden to include the metadata_generator constant field."""
        return self.model_dump(
            mode="json",
            by_alias=True,
            exclude_none=True,
            exclude_defaults=False,  # to include 'metadata_generator'
        )


class SessionArtifactManifest(BaseManifestModel):
    """Model for an artifact downloaded during the fetch-service session."""

    component_type: str = Field(alias="type")
    component_author: str
    component_vendor: str
    size: int
    url: list[str]


class CraftManifest(ProjectManifest):
    """Full manifest for a generated artifact.

    Includes project metadata and information on assets downloaded through a
    fetch-service session.
    """

    dependencies: list[SessionArtifactManifest]
