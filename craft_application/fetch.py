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
import io
import logging
import pathlib
import shlex
import subprocess
from dataclasses import dataclass
from functools import cache
from typing import Any, cast

import craft_providers
import craft_providers.lxd
import requests
from craft_cli import emit
from pydantic import Field
from requests.auth import HTTPBasicAuth

from craft_application import errors, util
from craft_application.models import CraftBaseModel
from craft_application.util import retry

logger = logging.getLogger(__name__)


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


_CERT_FILE_NAME = "local-ca.pem"
_KEY_FILE_NAME = "local-ca.key.pem"

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


class NetInfo:
    """Network and proxy info linking a fetch-service session and a build instance."""

    def __init__(
        self, instance: craft_providers.Executor, session_data: SessionData
    ) -> None:
        self._gateway = _get_gateway(instance)
        self._session_data = session_data

    @property
    def http_proxy(self) -> str:
        """Proxy string in the 'http://<session-id>:<session-token>@<ip>:<port>/."""
        session = self._session_data
        port = _DEFAULT_CONFIG.proxy
        gw = self._gateway
        return f"http://{session.session_id}:{session.token}@{gw}:{port}/"

    @staticmethod
    def env() -> dict[str, str]:
        """Environment variables to use for the proxy."""
        return {
            # Have go download directly from repositories
            "GOPROXY": "direct",
        }


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


def start_service() -> tuple[subprocess.Popen[str] | None, pathlib.Path]:
    """Start the fetch-service with default ports and auth.

    :returns: A tuple containing the fetch-service subprocess and a path to the proxy certificate.
    """
    if is_service_online():
        # Nothing to do, service is already up.
        return None, _get_certificate_dir() / _CERT_FILE_NAME

    # Check that the fetch service is actually installed
    verify_installed()

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

    cert, cert_key = _obtain_certificate()

    cmd.append(f"--cert={cert}")
    cmd.append(f"--key={cert_key}")

    # Accept permissive sessions
    cmd.append("--permissive-mode")

    # Shutdown after 5 minutes with no live sessions
    cmd.append("--idle-shutdown=300")

    log_filepath = get_log_filepath()
    log_filepath.parent.mkdir(parents=True, exist_ok=True)
    cmd.append(f"--log-file={log_filepath}")

    str_cmd = shlex.join(cmd)
    emit.debug(f"Launching fetch-service with '{str_cmd}'")

    fetch_process = subprocess.Popen(
        cmd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait a bit for the service to come online
    with contextlib.suppress(subprocess.TimeoutExpired):
        fetch_process.wait(0.5)

    if fetch_process.poll() is not None:
        # fetch-service already exited, something is wrong
        log = log_filepath.read_text()
        lines = log.splitlines()
        error_lines = [line for line in lines if "ERROR:" in line]
        error_text = "\n".join(error_lines)

        if "bind: address already in use" in error_text:
            proxy, control = _DEFAULT_CONFIG.proxy, _DEFAULT_CONFIG.control
            message = f"fetch-service ports {proxy} and {control} are already in use."
            details = None
        else:
            message = "Error spawning the fetch-service."
            details = error_text
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

    return fetch_process, cert


def stop_service(fetch_process: subprocess.Popen[str]) -> None:
    """Stop the fetch-service.

    This function first calls terminate(), and then kill() after a short time.
    """
    fetch_process.terminate()
    try:
        fetch_process.wait(timeout=1.0)
    except subprocess.TimeoutExpired:
        fetch_process.kill()


def create_session(*, strict: bool, timeout: float = 5.0) -> SessionData:
    """Create a new fetch-service session.

    :param strict: Whether the created session should be strict.
    :param timeout: Maximum time to wait for the response from the fetch-service
    :return: a SessionData object containing the session's id and token.
    """
    json = {"policy": "strict" if strict else "permissive"}
    data = _service_request("post", "session", json=json, timeout=timeout).json()

    return SessionData.unmarshal(data=data)


def teardown_session(
    session_data: SessionData, timeout: float = 10.0
) -> dict[str, Any]:
    """Stop and cleanup a running fetch-service session.

    :param session_data: the data of a previously-created session.
    :param timeout: Maximum time to wait for the response from the fetch-service
    :return: A dict containing the session's report (the contents and format
      of this dict are still subject to change).
    """
    session_id = session_data.session_id
    session_token = session_data.token

    # Revoke token
    _revoke_data = _service_request(
        "delete",
        f"session/{session_id}/token",
        json={"token": session_token},
        timeout=timeout,
    ).json()

    # Get session report
    session_report = _service_request(
        "get",
        f"session/{session_id}",
        json={},
        timeout=timeout,
    ).json()

    # Delete session
    _service_request("delete", f"session/{session_id}", timeout=timeout)

    # Delete session resources
    _service_request("delete", f"resources/{session_id}", timeout=timeout)

    return cast(dict[str, Any], session_report)


def get_log_filepath() -> pathlib.Path:
    """Get the path containing the fetch-service's output."""
    # All craft tools log to the same place, because it's a single fetch-service
    # instance. It needs to be a location that the fetch-service, as a strict
    # snap, can write to.
    logdir = _get_service_base_dir() / "craft-logs"
    logdir.mkdir(exist_ok=True, parents=True)
    return logdir / "fetch-service.log"


def verify_installed() -> None:
    """Verify that the fetch-service is installed, raising an error if it isn't."""
    if not _check_installed():
        raise errors.FetchServiceError(
            "The 'fetch-service' snap is not installed.",
            resolution=(
                "Install the fetch-service snap via "
                "'snap install --channel=candidate fetch-service'."
            ),
        )


def _service_request(
    verb: str,
    endpoint: str,
    json: dict[str, Any] | None = None,
    timeout: float = 10.0,
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
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as err:
        message = f"Error with fetch-service {verb.upper()}: {str(err)}"
        raise errors.FetchServiceError(message)

    return response


@cache
def _get_service_base_dir() -> pathlib.Path:
    """Get the base directory to contain the fetch-service's runtime files."""
    input_line = "sh -c 'echo $SNAP_USER_COMMON'"
    output = subprocess.check_output(
        ["snap", "run", "--shell", "fetch-service"], text=True, input=input_line
    )
    return pathlib.Path(output.strip())


def _get_gateway(instance: craft_providers.Executor) -> str:
    if not isinstance(instance, craft_providers.lxd.LXDInstance):
        raise TypeError("Don't know how to handle non-lxd instances")

    config = _get_config(instance)
    network_device = _get_network_name(config)

    route = subprocess.check_output(
        ["ip", "route", "show", "dev", network_device],
        text=True,
    )
    return route.strip().split()[-1]


def _get_config(instance: craft_providers.lxd.LXDInstance) -> dict[str, Any]:
    """Get the config for a lxc instance."""
    instance_name = instance.instance_name
    project = instance.project
    output = subprocess.check_output(
        ["lxc", "--project", project, "config", "show", instance_name, "--expanded"],
        text=True,
    )

    raw_config = util.safe_yaml_load(io.StringIO(output))

    if not isinstance(raw_config, dict):
        emit.trace(f"Config: {raw_config}")
        raise errors.FetchServiceError("Failed to parse LXD instance config.")

    return cast(dict[str, Any], raw_config)


def _get_network_name(config: dict[Any, Any]) -> str:
    """Get the network name of the default network device.

    LXD 4 and newer create the following default network device:
    eth0:
      name: eth0
      network: lxdbr0
      type: nic
    LXD 3 and older create the following default network device:
    eth0:
      name: eth0
      nictype: bridged
      parent: lxdbr0
      type: nic

    :param config: A dictionary of LXD configuration objects.

    :returns: The network name of the default network device.
    """
    try:
        device = config["devices"]["eth0"]
    except (KeyError, TypeError):
        raise errors.FetchServiceError("Couldn't find a network device named 'eth0'.")
    emit.debug(f"Parsing the network device 'eth0': {device}")

    if name := device.get("network"):
        return str(name)

    if name := device.get("parent"):
        return str(name)

    raise errors.FetchServiceError(
        message="Couldn't find the network name of the default network device.",
        resolution="Use a LXD installation with a default network configuration.",
    )


def _obtain_certificate() -> tuple[pathlib.Path, pathlib.Path]:
    """Retrieve, possibly creating, the certificate and key for the fetch service.

    :return: The full paths to the self-signed certificate and its private key.
    """
    cert_dir = _get_certificate_dir()

    cert_dir.mkdir(parents=True, exist_ok=True)

    cert = cert_dir / _CERT_FILE_NAME
    key = cert_dir / _KEY_FILE_NAME

    if cert.is_file() and key.is_file():
        # Certificate and key already generated
        # TODO check that the certificate hasn't expired  # noqa: FIX002
        return cert, key

    # At least one is missing, regenerate both
    key_tmp = cert_dir / "key-tmp.pem"
    cert_tmp = cert_dir / "cert-tmp.pem"

    # Create the key
    subprocess.run(
        [
            "openssl",
            "genrsa",
            "-aes256",
            "-passout",
            "pass:1",
            "-out",
            key_tmp,
            "4096",
        ],
        check=True,
        capture_output=True,
    )

    subprocess.run(
        [
            "openssl",
            "rsa",
            "-passin",
            "pass:1",
            "-in",
            key_tmp,
            "-out",
            key_tmp,
        ],
        check=True,
        capture_output=True,
    )

    # Create a certificate with the key
    subprocess.run(
        [
            "openssl",
            "req",
            "-subj",
            "/CN=root@localhost",
            "-key",
            key_tmp,
            "-new",
            "-x509",
            "-days",
            "7300",
            "-sha256",
            "-extensions",
            "v3_ca",
            "-out",
            cert_tmp,
        ],
        check=True,
        capture_output=True,
    )

    cert_tmp.rename(cert)
    key_tmp.rename(key)

    return cert, key


def _get_certificate_dir() -> pathlib.Path:
    """Get the location that should contain the fetch-service certificate and key."""
    base_dir = _get_service_base_dir()

    return base_dir / "craft/fetch-certificate"


def _check_installed() -> bool:
    """Check whether the fetch-service is installed."""
    return pathlib.Path(_FETCH_BINARY).is_file()
