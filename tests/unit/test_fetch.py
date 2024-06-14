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
import subprocess
from unittest.mock import call

import pytest
import responses
from craft_application import errors, fetch
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
    mock_base_dir = mocker.patch.object(
        fetch, "_get_service_base_dir", return_value=tmp_path
    )
    mock_get_status = mocker.patch.object(
        fetch, "get_service_status", return_value={"uptime": 10}
    )

    mock_popen = mocker.patch.object(subprocess, "Popen")
    mock_process = mock_popen.return_value
    mock_process.poll.return_value = None

    process = fetch.start_service()
    assert process is mock_process

    assert mock_is_online.called
    assert mock_base_dir.called
    assert mock_get_status.called

    popen_call = mock_popen.mock_calls[0]
    assert popen_call == call(
        [
            fetch._FETCH_BINARY,
            f"--control-port={CONTROL}",
            f"--proxy-port={PROXY}",
            f"--config={tmp_path/'config'}",
            f"--spool={tmp_path/'spool'}",
        ],
        env={"FETCH_SERVICE_AUTH": AUTH},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )


def test_start_service_already_up(mocker):
    """If the fetch-service is already up then a new process is *not* created."""
    mock_is_online = mocker.patch.object(fetch, "is_service_online", return_value=True)
    mock_popen = mocker.patch.object(subprocess, "Popen")

    assert fetch.start_service() is None

    assert mock_is_online.called
    assert not mock_popen.called


@assert_requests
def test_create_session():
    responses.add(
        responses.POST,
        f"http://localhost:{CONTROL}/session",
        json={"id": "my-session-id", "token": "my-session-token"},
        status=200,
    )

    session_data = fetch.create_session()

    assert session_data.session_id == "my-session-id"
    assert session_data.token == "my-session-token"


@assert_requests
def test_teardown_session():
    session_data = fetch.SessionData(id="my-session-id", token="my-session-token")

    # Call to delete token
    responses.delete(
        f"http://localhost:{CONTROL}/session/{session_data.session_id}/token",
        match=[matchers.json_params_matcher({"token": session_data.token})],
        json={},
        status=200,
    )
    # Call to get session report
    responses.get(
        f"http://localhost:{CONTROL}/session/{session_data.session_id}",
        json={},
        status=200,
    )
    # Call to delete session
    responses.delete(
        f"http://localhost:{CONTROL}/session/{session_data.session_id}",
        json={},
        status=200,
    )
    # Call to delete session resources
    responses.delete(
        f"http://localhost:{CONTROL}/resources/{session_data.session_id}",
        json={},
        status=200,
    )

    fetch.teardown_session(session_data)
