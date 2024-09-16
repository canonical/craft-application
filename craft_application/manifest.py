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
"""Functions to generate the craft manifest of an artifact."""

import hashlib
import pathlib
from datetime import datetime, timezone
from typing import Any

from craft_application.models import BuildInfo, Project
from craft_application.models.manifest import (
    CraftManifest,
    Hashes,
    ProjectManifest,
    SessionArtifactManifest,
)


def from_packed_artifact(
    project: Project, build_info: BuildInfo, artifact: pathlib.Path
) -> ProjectManifest:
    """Create the project manifest for a packed artifact."""
    hashes = _compute_hashes(artifact)

    now = datetime.now(timezone.utc)

    return ProjectManifest.unmarshal(
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


def from_session_report(report: dict[str, Any]) -> list[SessionArtifactManifest]:
    """Create session manifests from a fetch-session report."""
    artifacts: list[SessionArtifactManifest] = []
    for artifact in report["artefacts"]:
        metadata = artifact["metadata"]
        data = {
            "type": metadata["type"],
            "component-name": metadata["name"],
            "component-version": metadata["version"],
            "component-description": metadata["description"],
            "architecture": "TODO",
            "component-id": {
                "hashes": {"SHA1": metadata["sha1"], "SHA256": metadata["sha256"]}
            },
            "component-author": metadata["author"],
            "component-vendor": metadata["vendor"],
            "size": metadata["size"],
            "url": [d["url"] for d in artifact["downloads"]],
        }
        artifacts.append(SessionArtifactManifest.unmarshal(data))

    return artifacts


def create_craft_manifest(
    project_manifest_path: pathlib.Path, session_report: dict[str, Any]
) -> CraftManifest:
    """Create the full Craft manifest from a project and session report."""
    project = ProjectManifest.from_yaml_file(project_manifest_path)
    session_deps = from_session_report(session_report)

    data = {**project.marshal(), "dependencies": session_deps}
    return CraftManifest.model_validate(data)


def _compute_hashes(artifact: pathlib.Path) -> Hashes:
    read_bytes = artifact.read_bytes()

    return Hashes(
        SHA1=hashlib.sha1(  # noqa: S324 (insecure hash function)
            read_bytes
        ).hexdigest(),
        SHA256=hashlib.sha256(read_bytes).hexdigest(),
    )
