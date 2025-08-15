# Copyright 2025 Canonical Ltd.
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
"""A service for handling proxy configuration."""

from __future__ import annotations

import io
import pathlib
import subprocess
from typing import TYPE_CHECKING, final

from craft_cli import emit

from . import base

if TYPE_CHECKING:
    import craft_providers

# The path to the proxy certificate inside the build instance.
_PROXY_CERT_INSTANCE_PATH = pathlib.Path(
    "/usr/local/share/ca-certificates/local-ca.crt"
)


class ProxyService(base.AppService):
    """A service for handling proxy configuration."""

    __proxy_cert: pathlib.Path
    """Path to the CA certificate on the host."""

    __http_proxy: str
    """The http proxy to use."""

    __is_configured: bool = False
    """True if the proxy service has been configured."""

    @final
    def configure(self, proxy_cert: pathlib.Path, http_proxy: str) -> None:
        """Configure the proxy service.

        :param proxy_cert: The path to the proxy certificate to install in the instance.
        :param http_proxy: The proxy url to set in the instance.
        """
        self.__proxy_cert = proxy_cert
        self.__http_proxy = http_proxy
        self.__is_configured = True

    @final
    def configure_instance(self, instance: craft_providers.Executor) -> dict[str, str]:
        """Configure a build instance before the base image setup.

        :param instance: The instance to configure.

        :returns: A dict of environment variables to set in the instance.
        """
        if not self.__is_configured:
            emit.debug(
                "Skipping proxy configuration because the proxy service isn't configured."
            )
            return {}

        emit.progress("Configuring proxy in instance")

        self._install_certificate(instance)
        self._configure_apt(instance)
        self._configure_pip(instance)

        return self._env

    def finalize_instance_configuration(
        self, instance: craft_providers.Executor
    ) -> None:
        """Finish configuring a build instance after the base image setup.

        :param instance: The instance to configure.
        """
        if not self.__is_configured:
            emit.debug(
                "Skipping package configuration because the proxy service isn't configured."
            )
            return

        emit.progress("Finalizing instance configuration")

        self._configure_snapd(instance)

    @property
    def _env(self) -> dict[str, str]:
        """Environment variables to use for the proxy."""
        return {
            "http_proxy": self.__http_proxy,
            "https_proxy": self.__http_proxy,
            # This makes the requests lib take our cert into account.
            "REQUESTS_CA_BUNDLE": str(_PROXY_CERT_INSTANCE_PATH),
            # Same, but for cargo.
            "CARGO_HTTP_CAINFO": str(_PROXY_CERT_INSTANCE_PATH),
            # Have go download directly from repositories
            "GOPROXY": "direct",
        }

    def _configure_pip(self, instance: craft_providers.Executor) -> None:
        emit.progress("Configuring pip")

        self._execute_run(instance, ["mkdir", "-p", "/root/.pip"])
        pip_config = b"[global]\ncert=/usr/local/share/ca-certificates/local-ca.crt"
        instance.push_file_io(
            destination=pathlib.Path("/root/.pip/pip.conf"),
            content=io.BytesIO(pip_config),
            file_mode="0644",
        )

    def _configure_snapd(self, instance: craft_providers.Executor) -> None:
        """Configure snapd to use the proxy and see our certificate.

        Note: This must be called after _install_certificate(), to ensure that
        when the snapd restart happens the new cert is there.
        """
        emit.progress("Configuring snapd")
        self._execute_run(instance, ["systemctl", "restart", "snapd"])
        for config in ("proxy.http", "proxy.https"):
            self._execute_run(
                instance, ["snap", "set", "system", f"{config}={self.__http_proxy}"]
            )

    def _configure_apt(self, instance: craft_providers.Executor) -> None:
        """Configure the proxy for apt.

        This function is a no-op on systems without apt.
        """
        try:
            self._execute_run(instance, ["test", "-d", "/etc/apt"])
        except subprocess.CalledProcessError:
            emit.debug(
                "Not configuring the proxy for apt because apt isn't available in the instance."
            )
            return

        emit.progress("Configuring Apt")
        apt_config = f'Acquire::http::Proxy "{self.__http_proxy}";\n'
        apt_config += f'Acquire::https::Proxy "{self.__http_proxy}";\n'

        instance.push_file_io(
            destination=pathlib.Path("/etc/apt/apt.conf.d/99proxy"),
            content=io.BytesIO(apt_config.encode("utf-8")),
            file_mode="0644",
        )
        self._execute_run(instance, ["/bin/rm", "-Rf", "/var/lib/apt/lists"])

        emit.progress("Refreshing Apt package listings")
        self._execute_run(instance, ["apt", "update"])

    def _execute_run(
        self, instance: craft_providers.Executor, cmd: list[str]
    ) -> subprocess.CompletedProcess[str]:
        return instance.execute_run(  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
            cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

    def _install_certificate(self, instance: craft_providers.Executor) -> None:
        emit.progress("Installing certificate")
        emit.debug(
            f"Installing certificate from {str(self.__proxy_cert)!r} to "
            f"{str(_PROXY_CERT_INSTANCE_PATH)!r} in the instance."
        )

        if not self.__proxy_cert.exists():
            raise RuntimeError(
                f"Proxy certificate {str(self.__proxy_cert)!r} doesn't exist."
            )
        if not self.__proxy_cert.is_file():
            raise RuntimeError(
                f"Proxy certificate {str(self.__proxy_cert)!r} isn't a file."
            )

        self._execute_run(
            instance,
            ["mkdir", "-p", str(_PROXY_CERT_INSTANCE_PATH.parent)],
        )
        instance.push_file(
            source=self.__proxy_cert,
            destination=_PROXY_CERT_INSTANCE_PATH,
        )
        # Update the certificates db
        self._execute_run(
            instance, ["/bin/sh", "-c", "/usr/sbin/update-ca-certificates > /dev/null"]
        )
