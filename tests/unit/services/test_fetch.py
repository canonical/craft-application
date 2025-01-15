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
import contextlib
import json
import pathlib
import re
import textwrap
from datetime import datetime
from unittest import mock
from unittest.mock import MagicMock, call

import craft_providers
import pytest
from craft_providers import bases
from freezegun import freeze_time

from craft_application import ProviderService, fetch, services
from craft_application.models import BuildInfo
from craft_application.services import fetch as service_module


@pytest.fixture
def fetch_service(app, fake_services, fake_project):
    build_info = BuildInfo(
        platform="amd64",
        build_on="amd64",
        build_for="amd64",
        base=bases.BaseName("ubuntu", "24.04"),
    )
    return services.FetchService(
        app,
        fake_services,
        project=fake_project,
        build_plan=[build_info],
        session_policy="strict",
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


def test_teardown_session_create_manifest(
    fetch_service,
    tmp_path,
    mocker,
    manifest_data_dir,
    monkeypatch,
    fake_project,
    emitter,
):
    monkeypatch.chdir(tmp_path)

    # A lot of mock setup here but the goal is to have the fake fetch-service
    # session return the expected report, and the fake CraftManifest return the
    # expected data.

    # fetch.teardown_session returns a fake session report
    fake_report = json.loads((manifest_data_dir / "session-report.json").read_text())
    mocker.patch.object(fetch, "teardown_session", return_value=fake_report)

    # temporarily_pull_file returns a fake project manifest file
    project_manifest_path = manifest_data_dir / "project-expected.yaml"

    @contextlib.contextmanager
    def temporarily_pull_file(*, source, missing_ok):
        assert source == service_module._PROJECT_MANIFEST_MANAGED_PATH
        assert missing_ok
        yield project_manifest_path

    mock_instance = mock.Mock(spec=craft_providers.Executor)
    mock_instance.temporarily_pull_file = temporarily_pull_file

    fetch_service._session_data = {}
    fetch_service._instance = mock_instance

    fetch_service.teardown_session()

    expected_file = manifest_data_dir / "craft-manifest-expected.json"
    obtained_file = tmp_path / f"{fake_project.name}_{fake_project.version}_amd64.json"

    assert obtained_file.read_text() + "\n" == expected_file.read_text()

    expected_output = textwrap.dedent(
        """\
        The following artifacts were marked as rejected by the fetch-service:
        - url: https://github.com:443/canonical/sphinx-docs-starter-pack.git/git-upload-pack
          reasons:
          - fetch is allowed only on a single ref
          - fetch is only allowed with depth 1
          - git repository does not contain a go.mod file
        - url: https://proxy.golang.org:443/github.com/go-mmap/mmap/@v/v0.7.0.mod
          reasons:
          - the artifact format is unknown
          - the request was not recognized by any format inspector
        This build will fail on 'strict' fetch-service sessions.
        """
    )
    for line in expected_output.splitlines():
        emitter.assert_progress(
            line,
            permanent=True,
        )


@pytest.mark.parametrize("run_on_host", [True, False])
def test_warning_experimental(mocker, fetch_service, run_on_host, emitter):
    """The fetch-service warning should only be emitted when running on the host."""
    mocker.patch.object(fetch, "start_service")
    mocker.patch.object(fetch, "verify_installed")
    mocker.patch.object(fetch, "_get_service_base_dir", return_value=pathlib.Path())
    mocker.patch.object(ProviderService, "is_managed", return_value=not run_on_host)

    fetch_service.setup()

    logpath = fetch.get_log_filepath()
    warning = (
        "Warning: the fetch-service integration is experimental. "
        f"Logging output to {str(logpath)!r}."
    )
    warning_emitted = call("message", warning) in emitter.interactions

    assert warning_emitted == run_on_host


def test_setup_managed(mocker, fetch_service):
    """The fetch-service process should only be checked/started when running on the host."""
    mock_start = mocker.patch.object(fetch, "start_service")
    mocker.patch.object(ProviderService, "is_managed", return_value=True)

    fetch_service.setup()

    assert not mock_start.called
