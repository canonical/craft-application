#  This file is part of craft-application.
#
#  Copyright 2024 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Unit tests for the FetchService.

Note that most of the fetch-service functionality is already tested either on:
- unit/test_fetch.py, for unit tests of the endpoint calls, or;
- integration/services/test_fetch.py, for full integration tests.

As such, this module mostly unit-tests error paths coming from wrong usage of
the FetchService class.
"""
import re
from datetime import datetime
from unittest.mock import MagicMock

import pytest
from craft_application import fetch, services
from craft_application.models import BuildInfo
from craft_application.services import fetch as service_module
from craft_providers import bases
from freezegun import freeze_time


@pytest.fixture
def fetch_service(app, fake_services, fake_project):
    build_info = BuildInfo(
        platform="amd64",
        build_on="amd64",
        build_for="amd64",
        base=bases.BaseName("ubuntu", "24.04"),
    )
    return services.FetchService(
        app, fake_services, project=fake_project, build_plan=[build_info]
    )


def test_create_session_already_exists(fetch_service):
    fetch_service._session_data = fetch.SessionData(id="id", token="token")

    expected = re.escape(
        "create_session() called but there's already a live fetch-service session."
    )
    with pytest.raises(ValueError, match=expected):
        fetch_service.create_session(instance=MagicMock())


def test_teardown_session_no_session(fetch_service):
    expected = re.escape(
        "teardown_session() called with no live fetch-service session."
    )

    with pytest.raises(ValueError, match=expected):
        fetch_service.teardown_session()


@freeze_time(datetime.fromisoformat("2024-09-16T01:02:03.456789"))
def test_create_project_manifest(
    fetch_service, tmp_path, monkeypatch, manifest_data_dir
):
    manifest_path = tmp_path / "craft-project-manifest.yaml"
    monkeypatch.setattr(service_module, "_PROJECT_MANIFEST_MANAGED_PATH", manifest_path)
    monkeypatch.setenv("CRAFT_MANAGED_MODE", "1")

    artifact = tmp_path / "my-artifact.file"
    artifact.write_text("this is the generated artifact")

    assert not manifest_path.exists()
    fetch_service.create_project_manifest([artifact])

    assert manifest_path.is_file()
    expected = manifest_data_dir / "project-expected.yaml"

    assert manifest_path.read_text() == expected.read_text()


def test_create_project_manifest_not_managed(fetch_service, tmp_path, monkeypatch):
    manifest_path = tmp_path / "craft-project-manifest.yaml"
    monkeypatch.setattr(service_module, "_PROJECT_MANIFEST_MANAGED_PATH", manifest_path)
    monkeypatch.setenv("CRAFT_MANAGED_MODE", "0")

    artifact = tmp_path / "my-artifact.file"
    artifact.write_text("this is the generated artifact")

    assert not manifest_path.exists()
    fetch_service.create_project_manifest([artifact])
    assert not manifest_path.exists()
