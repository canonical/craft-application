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


_FETCH_BINARY = "/snap/bin/fetch-service"

_DEFAULT_CONFIG = FetchServiceConfig(
    proxy=13444,
    control=13555,
    username="craft",
    password="craft",  # noqa: S106 (hardcoded-password-func-arg)
)

# The path to the fetch-service's certificate inside the build instance.
_FETCH_CERT_INSTANCE_PATH = pathlib.Path(
    "/usr/local/share/ca-certificates/local-ca.crt"
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

    @property
    def env(self) -> dict[str, str]:
        """Environment variables to use for the proxy."""
        return {
            "http_proxy": self.http_proxy,
            "https_proxy": self.http_proxy,
            # This makes the requests lib take our cert into account.
            "REQUESTS_CA_BUNDLE": str(_FETCH_CERT_INSTANCE_PATH),
            # Same, but for cargo.
            "CARGO_HTTP_CAINFO": str(_FETCH_CERT_INSTANCE_PATH),
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


def start_service() -> subprocess.Popen[str] | None:
    """Start the fetch-service with default ports and auth."""
    if is_service_online():
        # Nothing to do, service is already up.
        return None

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
        fetch_process.wait(0.1)

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


def create_session(*, strict: bool) -> SessionData:
    """Create a new fetch-service session.

    :param strict: Whether the created session should be strict.
    :return: a SessionData object containing the session's id and token.
    """
    json = {"policy": "strict" if strict else "permissive"}
    data = _service_request("post", "session", json=json).json()

    return SessionData.unmarshal(data=data)


def teardown_session(session_data: SessionData) -> dict[str, Any]:
    """Stop and cleanup a running fetch-service session.

    :param session_data: the data of a previously-created session.
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


def configure_instance(
    instance: craft_providers.Executor, session_data: SessionData
) -> dict[str, str]:
    """Configure a build instance to use a given fetch-service session."""
    net_info = NetInfo(instance, session_data)

    _install_certificate(instance)
    _configure_pip(instance)
    _configure_snapd(instance, net_info)
    _configure_apt(instance, net_info)

    return net_info.env


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


@cache
def _get_service_base_dir() -> pathlib.Path:
    """Get the base directory to contain the fetch-service's runtime files."""
    input_line = "sh -c 'echo $SNAP_USER_COMMON'"
    output = subprocess.check_output(
        ["snap", "run", "--shell", "fetch-service"], text=True, input=input_line
    )
    return pathlib.Path(output.strip())


def _install_certificate(instance: craft_providers.Executor) -> None:

    logger.info("Installing certificate")
    # Push the local certificate
    cert, _key = _obtain_certificate()
    instance.push_file(
        source=cert,
        destination=_FETCH_CERT_INSTANCE_PATH,
    )
    # Update the certificates db
    _execute_run(
        instance, ["/bin/sh", "-c", "/usr/sbin/update-ca-certificates > /dev/null"]
    )


def _configure_pip(instance: craft_providers.Executor) -> None:
    logger.info("Configuring pip")

    _execute_run(instance, ["mkdir", "-p", "/root/.pip"])
    pip_config = b"[global]\ncert=/usr/local/share/ca-certificates/local-ca.crt"
    instance.push_file_io(
        destination=pathlib.Path("/root/.pip/pip.conf"),
        content=io.BytesIO(pip_config),
        file_mode="0644",
    )


def _configure_snapd(instance: craft_providers.Executor, net_info: NetInfo) -> None:
    """Configure snapd to use the proxy and see our certificate.

    Note: This *must* be called *after* _install_certificate(), to ensure that
    when the snapd restart happens the new cert is there.
    """
    logger.info("Configuring snapd")
    _execute_run(instance, ["systemctl", "restart", "snapd"])
    for config in ("proxy.http", "proxy.https"):
        _execute_run(
            instance, ["snap", "set", "system", f"{config}={net_info.http_proxy}"]
        )


def _configure_apt(instance: craft_providers.Executor, net_info: NetInfo) -> None:
    logger.info("Configuring Apt")
    apt_config = f'Acquire::http::Proxy "{net_info.http_proxy}";\n'
    apt_config += f'Acquire::https::Proxy "{net_info.http_proxy}";\n'

    instance.push_file_io(
        destination=pathlib.Path("/etc/apt/apt.conf.d/99proxy"),
        content=io.BytesIO(apt_config.encode("utf-8")),
        file_mode="0644",
    )
    _execute_run(instance, ["/bin/rm", "-Rf", "/var/lib/apt/lists"])

    logger.info("Refreshing Apt package listings")
    _execute_run(instance, ["apt", "update"])


def _get_gateway(instance: craft_providers.Executor) -> str:
    from craft_providers.lxd import LXDInstance

    if not isinstance(instance, LXDInstance):
        raise TypeError("Don't know how to handle non-lxd instances")

    instance_name = instance.instance_name
    project = instance.project
    output = subprocess.check_output(
        ["lxc", "--project", project, "config", "show", instance_name, "--expanded"],
        text=True,
    )
    config = util.safe_yaml_load(io.StringIO(output))
    network = config["devices"]["eth0"]["network"]

    route = subprocess.check_output(
        ["ip", "route", "show", "dev", network],
        text=True,
    )
    return route.strip().split()[-1]


def _obtain_certificate() -> tuple[pathlib.Path, pathlib.Path]:
    """Retrieve, possibly creating, the certificate and key for the fetch service.

    :return: The full paths to the self-signed certificate and its private key.
    """
    cert_dir = _get_certificate_dir()

    cert_dir.mkdir(parents=True, exist_ok=True)

    cert = cert_dir / "local-ca.pem"
    key = cert_dir / "local-ca.key.pem"

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


def _execute_run(
    instance: craft_providers.Executor, cmd: list[str]
) -> subprocess.CompletedProcess[str]:
    return instance.execute_run(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
        cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
    )
