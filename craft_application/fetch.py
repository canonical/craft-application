# This file is part of craft_application.
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
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Utilities to interact with the fetch-service."""
import contextlib
import pathlib
import subprocess
from dataclasses import dataclass
from typing import Any, cast

import requests
from pydantic import Field
from requests.auth import HTTPBasicAuth

from craft_application import errors
from craft_application.models import CraftBaseModel
from craft_application.util import retry


@dataclass(frozen=True)
class FetchServiceConfig:
    """Dataclass for the ports that a fetch-service instance uses."""

    proxy: int
    """The proxy port, to be passed to the applications to be proxied."""
    control: int
    """The control port, to create/terminate sessions, get status, etc."""
    username: str
    """The username for auth."""
    password: str
    """The password for auth."""

    @property
    def auth(self) -> str:
        """Authentication in user:passwd format."""
        return f"{self.username}:{self.password}"


_FETCH_BINARY = "/snap/bin/fetch-service"

_DEFAULT_CONFIG = FetchServiceConfig(
    proxy=13444,
    control=13555,
    username="craft",
    password="craft",  # noqa: S106 (hardcoded-password-func-arg)
)


class SessionData(CraftBaseModel):
    """Fetch service session data."""

    session_id: str = Field(alias="id")
    token: str


def is_service_online() -> bool:
    """Whether the fetch-service is up and listening."""
    try:
        status = get_service_status()
    except errors.FetchServiceError:
        return False
    return "uptime" in status


def get_service_status() -> dict[str, Any]:
    """Get the JSON status of the fetch-service.

    :raises errors.FetchServiceError: if a connection error happens.
    """
    response = _service_request("get", "status")
    return cast(dict[str, Any], response.json())


def start_service() -> subprocess.Popen[str] | None:
    """Start the fetch-service with default ports and auth."""
    if is_service_online():
        # Nothing to do, service is already up.
        return None

    cmd = [_FETCH_BINARY]

    env = {"FETCH_SERVICE_AUTH": _DEFAULT_CONFIG.auth}

    # Add the ports
    cmd.append(f"--control-port={_DEFAULT_CONFIG.control}")
    cmd.append(f"--proxy-port={_DEFAULT_CONFIG.proxy}")

    # Set config and spool directories
    base_dir = _get_service_base_dir()

    for dir_name in ("config", "spool"):
        dir_path = base_dir / dir_name
        dir_path.mkdir(exist_ok=True)
        cmd.append(f"--{dir_name}={dir_path}")

    fetch_process = subprocess.Popen(
        cmd, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )

    # Wait a bit for the service to come online
    with contextlib.suppress(subprocess.TimeoutExpired):
        fetch_process.wait(0.1)

    if fetch_process.poll() is not None:
        # fetch-service already exited, something is wrong
        stdout = ""
        if fetch_process.stdout is not None:
            stdout = fetch_process.stdout.read()

        if "bind: address already in use" in stdout:
            proxy, control = _DEFAULT_CONFIG.proxy, _DEFAULT_CONFIG.control
            message = f"fetch-service ports {proxy} and {control} are already in use."
            details = None
        else:
            message = "Error spawning the fetch-service."
            details = stdout
        raise errors.FetchServiceError(message, details=details)

    status = retry(
        "wait for fetch-service to come online",
        errors.FetchServiceError,
        get_service_status,  # pyright: ignore[reportArgumentType]
    )
    if "uptime" not in status:
        stop_service(fetch_process)
        raise errors.FetchServiceError(
            f"Fetch service did not start correctly: {status}"
        )

    return fetch_process


def stop_service(fetch_process: subprocess.Popen[str]) -> None:
    """Stop the fetch-service.

    This function first calls terminate(), and then kill() after a short time.
    """
    fetch_process.terminate()
    try:
        fetch_process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        fetch_process.kill()


def create_session() -> SessionData:
    """Create a new fetch-service session.

    :return: a SessionData object containing the session's id and token.
    """
    data = _service_request("post", "session", json={}).json()

    return SessionData.unmarshal(data=data)


def teardown_session(session_data: SessionData) -> dict[str, Any]:
    """Stop and cleanup a running fetch-service session.

    :param SessionData: the data of a previously-created session.
    :return: A dict containing the session's report (the contents and format
      of this dict are still subject to change).
    """
    session_id = session_data.session_id
    session_token = session_data.token

    # Revoke token
    _revoke_data = _service_request(
        "delete", f"session/{session_id}/token", json={"token": session_token}
    ).json()

    # Get session report
    session_report = _service_request("get", f"session/{session_id}", json={}).json()

    # Delete session
    _service_request("delete", f"session/{session_id}")

    # Delete session resources
    _service_request("delete", f"resources/{session_id}")

    return cast(dict[str, Any], session_report)


def _service_request(
    verb: str, endpoint: str, json: dict[str, Any] | None = None
) -> requests.Response:
    headers = {
        "Content-type": "application/json",
    }
    auth = HTTPBasicAuth(_DEFAULT_CONFIG.username, _DEFAULT_CONFIG.password)
    try:
        response = requests.request(
            verb,
            f"http://localhost:{_DEFAULT_CONFIG.control}/{endpoint}",
            auth=auth,
            headers=headers,
            json=json,  # Use defaults
            timeout=0.1,
        )
        response.raise_for_status()
    except requests.RequestException as err:
        message = f"Error with fetch-service {verb.upper()}: {str(err)}"
        raise errors.FetchServiceError(message)

    return response


def _get_service_base_dir() -> pathlib.Path:
    """Get the base directory to contain the fetch-service's runtime files."""
    input_line = "sh -c 'echo $SNAP_USER_COMMON'"
    output = subprocess.check_output(
        ["snap", "run", "--shell", "fetch-service"], text=True, input=input_line
    )
    return pathlib.Path(output.strip())
