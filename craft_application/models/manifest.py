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
import hashlib
import pathlib
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import Field
from typing_extensions import Self, override

from craft_application import models
from craft_application.models import CraftBaseModel


class Hashes(CraftBaseModel):
    """Digests identifying an artifact/asset."""

    sha1: str
    sha256: str

    @classmethod
    def from_path(cls, path: pathlib.Path) -> Self:
        """Compute digests for a given path."""
        read_bytes = path.read_bytes()

        return cls(
            sha1=hashlib.sha1(  # noqa: S324 (insecure hash function)
                read_bytes
            ).hexdigest(),
            sha256=hashlib.sha256(read_bytes).hexdigest(),
        )


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

    @classmethod
    def from_packed_artifact(
        cls,
        project: models.Project,
        build_info: models.BuildInfo,
        artifact: pathlib.Path,
    ) -> Self:
        """Create the project manifest for a packed artifact."""
        hashes = Hashes.from_path(artifact)

        now = datetime.now(timezone.utc)

        return cls.unmarshal(
            {
                "component-name": project.name,
                "component-version": project.version,
                "component-description": project.summary,
                "component-id": {"hashes": hashes.marshal()},
                "architecture": build_info.build_for,
                "license": project.license,
                "creation_timestamp": now.isoformat(),
            }
        )


class SessionArtifactManifest(BaseManifestModel):
    """Model for an artifact downloaded during the fetch-service session."""

    component_type: str = Field(alias="type")
    component_author: str
    component_vendor: str
    size: int
    url: list[str]
    rejected: bool = Field(exclude=True)
    rejection_reasons: list[str] = Field(exclude=True)

    @classmethod
    def from_session_report(cls, report: dict[str, Any]) -> list[Self]:
        """Create session manifests from a fetch-session report."""
        artifacts: list[Self] = []

        for artifact in report["artifacts"]:
            # Figure out if the artifact was rejected, and for which reasons
            rejected = artifact.get("result") == "Rejected"
            reasons: set[str] = set()
            if rejected:
                reasons.update(_get_reasons(artifact.get("request-inspection", {})))
                reasons.update(_get_reasons(artifact.get("response-inspection", {})))

            metadata = artifact["metadata"]
            data = {
                "type": metadata["type"],
                "component-name": metadata["name"],
                "component-version": metadata["version"],
                "component-description": metadata["description"],
                # "architecture" is only present on the metadata if applicable.
                "architecture": metadata.get("architecture", ""),
                "component-id": {
                    "hashes": {"sha1": metadata["sha1"], "sha256": metadata["sha256"]}
                },
                "component-author": metadata["author"],
                "component-vendor": metadata["vendor"],
                "size": metadata["size"],
                "url": [d["url"] for d in artifact["downloads"]],
                "rejected": rejected,
                "rejection-reasons": sorted(reasons),
            }
            artifacts.append(cls.unmarshal(data))

        return artifacts


class CraftManifest(ProjectManifest):
    """Full manifest for a generated artifact.

    Includes project metadata and information on assets downloaded through a
    fetch-service session.
    """

    dependencies: list[SessionArtifactManifest]

    @classmethod
    def create_craft_manifest(
        cls, project_manifest_path: pathlib.Path, session_report: dict[str, Any]
    ) -> Self:
        """Create the full Craft manifest from a project and session report."""
        project = ProjectManifest.from_yaml_file(project_manifest_path)
        session_deps = SessionArtifactManifest.from_session_report(session_report)

        data = {**project.marshal(), "dependencies": session_deps}
        return cls.model_validate(data)


def _get_reasons(inspections: dict[str, Any]) -> set[str]:
    reasons: set[str] = set()

    for inspection in inspections.values():
        if inspection.get("opinion") in ("Rejected", "Unknown"):
            reasons.add(inspection["reason"])

    return reasons
