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
import json
import pathlib
from datetime import datetime

import pytest
from craft_application import util
from craft_application.models import BuildInfo
from craft_application.models.manifest import (
    CraftManifest,
    ProjectManifest,
    SessionArtifactManifest,
)
from craft_providers import bases
from freezegun import freeze_time

TEST_DATA_DIR = pathlib.Path(__file__).parent / "data/manifest"


@pytest.fixture
# @freeze_time("2024-09-16T01:02:03.456789")
@freeze_time(datetime.fromisoformat("2024-09-16T01:02:03.456789"))
def project_manifest(tmp_path, fake_project):
    project = fake_project
    build_info = BuildInfo(
        platform="amd64",
        build_on="amd64",
        build_for="amd64",
        base=bases.BaseName("ubuntu", "24.04"),
    )

    artifact = tmp_path / "my-artifact.file"
    artifact.write_text("this is the generated artifact")

    return ProjectManifest.from_packed_artifact(project, build_info, artifact)


@pytest.fixture
def session_report():
    report_path = TEST_DATA_DIR / "session-report.json"
    return json.loads(report_path.read_text())


def test_from_packed_artifact(project_manifest):
    expected = (TEST_DATA_DIR / "project-expected.yaml").read_text()
    obtained = project_manifest.to_yaml_string()

    assert obtained == expected


def test_from_session_report(session_report):
    deps = SessionArtifactManifest.from_session_report(session_report)
    obtained = util.dump_yaml([d.marshal() for d in deps])

    expected = (TEST_DATA_DIR / "session-manifest-expected.yaml").read_text()
    assert obtained == expected


def test_create_craft_manifest(tmp_path, project_manifest, session_report):
    project_manifest_path = tmp_path / "project-manifest.yaml"
    project_manifest.to_yaml_file(project_manifest_path)

    craft_manifest = CraftManifest.create_craft_manifest(
        project_manifest_path, session_report
    )

    obtained = json.dumps(craft_manifest.marshal(), indent=2) + "\n"
    expected = (TEST_DATA_DIR / "craft-manifest-expected.json").read_text()

    assert obtained == expected
