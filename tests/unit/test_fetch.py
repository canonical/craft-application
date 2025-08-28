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
"""Tests for fetch-service-related functions."""

import re
import subprocess
import textwrap
from pathlib import Path
from unittest import mock
from unittest.mock import call

import pytest
import responses
from craft_application import errors, fetch
from craft_providers.lxd import LXDInstance
from responses import matchers

CONTROL = fetch._DEFAULT_CONFIG.control
PROXY = fetch._DEFAULT_CONFIG.proxy
AUTH = fetch._DEFAULT_CONFIG.auth

assert_requests = responses.activate(assert_all_requests_are_fired=True)


@assert_requests
def test_get_service_status_success():
    responses.add(
        responses.GET,
        f"http://localhost:{CONTROL}/status",
        json={"uptime": 10},
        status=200,
    )
    status = fetch.get_service_status()
    assert status == {"uptime": 10}


@assert_requests
def test_get_service_status_failure():
    responses.add(
        responses.GET,
        f"http://localhost:{CONTROL}/status",
        status=404,
    )
    expected = "Error with fetch-service GET: 404 Client Error"
    with pytest.raises(errors.FetchServiceError, match=expected):
        fetch.get_service_status()


@pytest.mark.parametrize(
    ("status", "json", "expected"),
    [
        (200, {"uptime": 10}, True),
        (200, {"uptime": 10, "other-key": "value"}, True),
        (200, {"other-key": "value"}, False),
        (404, {"other-key": "value"}, False),
    ],
)
@assert_requests
def test_is_service_online(status, json, expected):
    responses.add(
        responses.GET,
        f"http://localhost:{CONTROL}/status",
        status=status,
        json=json,
    )
    assert fetch.is_service_online() == expected


def test_start_service(mocker, tmp_path):
    mock_is_online = mocker.patch.object(fetch, "is_service_online", return_value=False)
    mocker.patch.object(fetch, "_check_installed", return_value=True)
    mock_base_dir = mocker.patch.object(
        fetch, "_get_service_base_dir", return_value=tmp_path
    )
    mock_get_status = mocker.patch.object(
        fetch, "get_service_status", return_value={"uptime": 10}
    )

    fake_cert, fake_key = tmp_path / "cert.crt", tmp_path / "key.pem"
    mock_obtain_certificate = mocker.patch.object(
        fetch, "_obtain_certificate", return_value=(fake_cert, fake_key)
    )

    mock_popen = mocker.patch.object(subprocess, "Popen")
    mock_process = mock_popen.return_value
    mock_process.poll.return_value = None

    process, proxy_cert = fetch.start_service()
    assert process is mock_process
    assert proxy_cert == tmp_path / "cert.crt"

    assert mock_is_online.called
    assert mock_base_dir.called
    assert mock_get_status.called
    assert mock_obtain_certificate.called

    popen_call = mock_popen.mock_calls[0]
    assert popen_call == call(
        [
            fetch._FETCH_BINARY,
            f"--control-port={CONTROL}",
            f"--proxy-port={PROXY}",
            f"--config={tmp_path / 'config'}",
            f"--spool={tmp_path / 'spool'}",
            f"--cert={fake_cert}",
            f"--key={fake_key}",
            "--permissive-mode",
            "--idle-shutdown=300",
            f"--log-file={tmp_path / 'craft-logs/fetch-service.log'}",
        ],
        env={
            "FETCH_SERVICE_AUTH": AUTH,
        },
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def test_start_service_already_up(mocker, tmp_path):
    """If the fetch-service is already up then a new process is *not* created."""
    mocker.patch.object(fetch, "_get_service_base_dir", return_value=tmp_path)
    mock_is_online = mocker.patch.object(fetch, "is_service_online", return_value=True)
    mock_popen = mocker.patch.object(subprocess, "Popen")

    process, proxy_cert = fetch.start_service()

    assert process is None
    assert proxy_cert == tmp_path / "craft/fetch-certificate/local-ca.pem"

    assert mock_is_online.called
    assert not mock_popen.called


def test_start_service_not_installed(mocker):
    mocker.patch.object(fetch, "is_service_online", return_value=False)
    mocker.patch.object(fetch, "_check_installed", return_value=False)

    expected = re.escape("The 'fetch-service' snap is not installed.")
    with pytest.raises(errors.FetchServiceError, match=expected):
        fetch.start_service()


@assert_requests
@pytest.mark.parametrize(
    ("strict", "expected_policy"), [(True, "strict"), (False, "permissive")]
)
def test_create_session(strict, expected_policy):
    create_session_timeout = 5.0
    responses.add(
        responses.POST,
        f"http://localhost:{CONTROL}/session",
        json={"id": "my-session-id", "token": "my-session-token"},
        status=200,
        match=[
            matchers.json_params_matcher({"policy": expected_policy}),
            matchers.request_kwargs_matcher({"timeout": create_session_timeout}),
        ],
    )

    session_data = fetch.create_session(strict=strict)

    assert session_data.session_id == "my-session-id"
    assert session_data.token == "my-session-token"  # noqa: S105


@assert_requests
def test_teardown_session():
    session_data = fetch.SessionData(id="my-session-id", token="my-session-token")  # noqa: S106
    default_timeout = 10.0

    # Call to delete token
    responses.delete(
        f"http://localhost:{CONTROL}/session/{session_data.session_id}/token",
        match=[
            matchers.json_params_matcher({"token": session_data.token}),
            matchers.request_kwargs_matcher({"timeout": default_timeout}),
        ],
        json={},
        status=200,
    )
    # Call to get session report
    responses.get(
        f"http://localhost:{CONTROL}/session/{session_data.session_id}",
        json={},
        match=[matchers.request_kwargs_matcher({"timeout": default_timeout})],
        status=200,
    )
    # Call to delete session
    responses.delete(
        f"http://localhost:{CONTROL}/session/{session_data.session_id}",
        json={},
        match=[matchers.request_kwargs_matcher({"timeout": default_timeout})],
        status=200,
    )
    # Call to delete session resources
    responses.delete(
        f"http://localhost:{CONTROL}/resources/{session_data.session_id}",
        json={},
        match=[matchers.request_kwargs_matcher({"timeout": default_timeout})],
        status=200,
    )

    fetch.teardown_session(session_data)


def test_get_certificate_dir(mocker):
    mocker.patch.object(
        fetch,
        "_get_service_base_dir",
        return_value=Path("/home/user/snap/fetch-service/common"),
    )
    cert_dir = fetch._get_certificate_dir()

    expected = Path("/home/user/snap/fetch-service/common/craft/fetch-certificate")
    assert cert_dir == expected


@pytest.mark.parametrize(
    "config",
    [
        pytest.param(
            textwrap.dedent(
                """
                devices:
                  eth0:
                    name: eth0
                    network: lxdbr0
                    type: nic
                """
            ),
            id="default-device",
        ),
        pytest.param(
            textwrap.dedent(
                """
                devices:
                  eth0:
                    name: eth0
                    nictype: bridged
                    parent: lxdbr0
                    type: nic
                """
            ),
            id="old-default-device",
        ),
    ],
)
def test_get_gateway(mocker, config):
    gateway = "10.207.202.1"
    ip_route = f"10.207.202.0/24 proto kernel scope link src {gateway}"
    mocker.patch.object(
        subprocess,
        "run",
        side_effect=[mock.Mock(stdout=text) for text in [config, ip_route]],
    )

    actual_gateway = fetch._get_gateway(LXDInstance(name="test-instance"))

    assert gateway == actual_gateway


@pytest.mark.parametrize(
    ("config", "expected_error"),
    [
        pytest.param(
            "name: test-name",
            "Couldn't find a network device named 'eth0'.",
            id="no-devices",
        ),
        pytest.param(
            textwrap.dedent(
                """
                name: test-name
                devices:
                  custom:
                    name: wrong-device
                """
            ),
            "Couldn't find a network device named 'eth0'.",
            id="missing-eth0",
        ),
        pytest.param(
            textwrap.dedent(
                """
                name: test-name
                devices:
                  eth0:
                    name: test-device
                """
            ),
            "Couldn't find the network name of the default network device.",
            id="missing-network-name",
        ),
    ],
)
def test_get_gateway_errors(config, expected_error, mocker):
    mocker.patch.object(subprocess, "run", side_effect=[mock.Mock(stdout=config)])

    with pytest.raises(errors.FetchServiceError, match=expected_error):
        fetch._get_gateway(LXDInstance(name="test-instance"))
