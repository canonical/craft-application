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
from craft_application import errors, fetch, services
from craft_application.services import fetch as service_module
from craft_application.services.fetch import (
    EXTERNAL_FETCH_SERVICE_ENV_VAR,
    PROXY_CERT_ENV_VAR,
)
from freezegun import freeze_time


@pytest.fixture
def fetch_service(app, fake_services, fake_project):
    return services.FetchService(
        app,
        fake_services,
    )


@pytest.mark.parametrize("policy", ["strict", "permissive"])
def test_set_policy(fetch_service, policy):
    assert fetch_service._session_policy == "strict"

    fetch_service.set_policy(policy)

    assert fetch_service._session_policy == policy


def test_create_session_already_exists(fetch_service):
    fetch_service._session_data = fetch.SessionData(id="id", token="token")  # noqa: S106

    expected = re.escape(
        "create_session() called but there's already a live fetch-service session."
    )
    with pytest.raises(ValueError, match=expected):
        fetch_service.create_session(instance=MagicMock())


def test_create_session(fetch_service, mocker):
    """Create a session and configure the proxy service."""
    session_data = fetch.SessionData(id="id", token="token")  # noqa: S106
    mocker.patch.object(fetch, "create_session", return_value=session_data)
    mocker.patch.object(fetch, "_get_gateway", return_value="test-gateway")
    mock_configure_proxy = mocker.patch.object(services.ProxyService, "configure")
    proxy_cert = pathlib.Path("test-cert.pem")
    fetch_service._proxy_cert = proxy_cert

    env = fetch_service.create_session(instance=MagicMock())

    mock_configure_proxy.assert_called_once_with(
        proxy_cert, "http://id:token@test-gateway:13444/"
    )
    assert env == {"GOPROXY": "direct"}


def test_create_session_not_setup(fetch_service):
    """Error if the create_session is called before the fetch service is setup."""
    expected_error = re.escape(
        "create_session() was called before setting up the fetch service."
    )

    with pytest.raises(ValueError, match=expected_error):
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
    obtained_file = (
        tmp_path / f"{fake_project.name}_{fake_project.version}_64-bit-pc.json"
    )

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
def test_warning_experimental(mocker, fetch_service, run_on_host, emitter, tmp_path):
    """The fetch-service warning should only be emitted when running on the host."""
    mocker.patch.object(fetch, "start_service", return_value=(None, tmp_path))
    mocker.patch.object(fetch, "verify_installed")
    mocker.patch.object(fetch, "_get_service_base_dir", return_value=pathlib.Path())
    mocker.patch("craft_application.util.is_managed_mode", return_value=not run_on_host)

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
    mocker.patch("craft_application.util.is_managed_mode", return_value=True)

    fetch_service.setup()

    assert not mock_start.called


@pytest.mark.parametrize(
    ("enable_command_line", "env_var_value", "expected_active"),
    [
        pytest.param(True, None, True, id="command line only"),
        pytest.param(False, "1", True, id="env var only"),
        pytest.param(False, None, False, id="neither"),
    ],
)
def test_is_active(
    fetch_service, monkeypatch, enable_command_line, env_var_value, expected_active
):
    monkeypatch.setenv(EXTERNAL_FETCH_SERVICE_ENV_VAR, env_var_value)
    is_active = fetch_service.is_active(enable_command_line=enable_command_line)
    assert is_active == expected_active


def test_is_active_both(fetch_service, monkeypatch):
    """Trying to set both CRAFT_USE_EXTERNAL_FETCH_SERVICE *and* --enable-fetch-service.

    This is currently unsupported because the two code paths are too tied together.
    """
    monkeypatch.setenv(EXTERNAL_FETCH_SERVICE_ENV_VAR, "1")
    with pytest.raises(errors.CraftError):
        fetch_service.is_active(enable_command_line=True)


def test_configure_session_external(
    fetch_service, mocker, fake_services, monkeypatch, tmp_path
):
    fake_cert = tmp_path / "local-ca.crt"
    fake_cert.touch()

    proxy_service = fake_services.get("proxy")
    spied_configure = mocker.spy(proxy_service, "configure")

    monkeypatch.setenv(EXTERNAL_FETCH_SERVICE_ENV_VAR, "1")
    monkeypatch.setenv(PROXY_CERT_ENV_VAR, str(fake_cert))
    monkeypatch.setenv("http_proxy", "www.example.com")
    fetch_service.setup()

    env = fetch_service.configure_instance(instance=MagicMock())

    assert env == fetch.NetInfo.env()
    spied_configure.assert_called_once_with(fake_cert, "www.example.com")
