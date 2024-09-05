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
"""Handling of Ubuntu Pro Services"""
from __future__ import annotations
from typing import Any

from craft_application.errors import (
    UbuntuProClientNotFound,
    UbuntuProApiException,
    UbuntuProDetached,
    UbuntuProAttached,
    InvalidUbuntuProServices,
)
import logging
import subprocess as sub
import json
from pathlib import Path

logger = logging.getLogger(__name__)

# list of locations to search for paths
PRO_CLIENT_PATHS = [
    Path("/usr/bin/ubuntu-advantage"),
    Path("/usr/bin/ua"),
    Path("/usr/bin/pro"),
]


class ProServices(set[str]):
    """Class for managing pro-services within the lifecycle."""

    # pro binary to use for calls
    # TODO: will we support this executable long term?

    # placeholder for empty sets
    empty_placeholder = "none"

    # ignore services outside of this scope
    build_service_scope: set[str] = {
        "esm-apps",
        "esm-infa",
        "fips-preview",
        "fips-updates",
    }

    # location of pro client
    pro_executable: Path | None = next(
        (path for path in PRO_CLIENT_PATHS if path.exists()), None
    )
    # locations to check for pro client

    def __str__(self) -> str:
        """Convert to string for display to user."""

        result = ", ".join(self) if self else self.empty_placeholder

        return result

    @classmethod
    def from_csv(cls, services: str) -> ProServices:
        """Create a new ProServices instance from a csv string."""

        split = [service.strip() for service in services.split(",")]
        result = cls(split)

        return result

    @classmethod
    def pro_client_exists(cls) -> bool:
        """Check if Ubuntu Pro executable exists or not."""
        result = cls.pro_executable is not None and cls.pro_executable.exists()

        return result

    @classmethod
    def _log_processes(cls, process: sub.CompletedProcess) -> None:  # pyright: ignore
        # TODO: Fix pyright warnings
        logger.error(
            "Ubuntu Pro Client Response: \n"
            f"Return Code: {process.returncode}\n"
            f"StdOut:\n{process.stdout}\n\n"  # pyright: ignore
            f"StdErr:\n{process.stderr}\n\n"  # pyright: ignore
        )

    @classmethod
    def _pro_api_call(cls, endpoint: str) -> dict[str, Any]:
        """Call Ubuntu Pro executable and parse response"""

        if not cls.pro_client_exists():
            raise UbuntuProClientNotFound(str(cls.pro_executable))

        try:
            proc = sub.run(
                [str(cls.pro_executable), "api", endpoint],
                capture_output=True,
                text=True,
            )
        except Exception as exc:
            raise UbuntuProApiException(
                f'An error occurred while executing "{cls.pro_executable}"'
            ) from exc

        if proc.returncode != 0:
            cls._log_processes(proc)  # pyright: ignore
            raise UbuntuProApiException(
                f"The Pro Client returned a non-zero status: {proc.returncode}. "
                "See log for more details"
            )

        try:
            result = json.loads(proc.stdout)

        except json.decoder.JSONDecodeError as exc:
            cls._log_processes(proc)  # pyright: ignore
            raise UbuntuProApiException(
                f"Could not parse JSON response from Ubuntu Pro client. "
                "See log for more details"
            )

        if result["result"] != "success":
            cls._log_processes(proc)  # pyright: ignore
            raise UbuntuProApiException(
                f"Ubuntu Pro API returned an error response. See log for more details"
            )

        return result

    @classmethod
    def pro_attached(cls) -> bool:
        """Returns True if environment is attached to Ubuntu Pro."""

        response = cls._pro_api_call("u.pro.status.is_attached.v1")
        result = response["data"]["attributes"]["is_attached"]

        return result  # pyright: ignore

    @classmethod
    def pro_services(cls) -> ProServices:
        """Return set of enabled Ubuntu Pro services in the environment.
        The returned set only includes services relevant to lifecycle commands."""

        response = cls._pro_api_call("u.pro.status.enabled_services.v1")
        enabled_services = response["data"]["attributes"]["enabled_services"]

        service_names = {service["name"] for service in enabled_services}

        # remove any services that aren't relevant to build services
        service_names = service_names.intersection(cls.build_service_scope)

        result = cls(service_names)

        return result

    def validate(self):
        """Validate the environment against pro services specified in this ProServices instance."""

        # TODO: add logging
        try:
            # first, check Ubuntu Pro status
            # Since we extend the set class, cast ourselves to bool to check if we empty. if we are not
            # empty, this implies we require pro services.
            if self.pro_attached() != bool(self):
                if self:
                    raise UbuntuProDetached()
                else:
                    raise UbuntuProAttached()

            # If we are not attached, we can infer that services are disabled
            if not self:
                return

            # second, check that the set of enabled pro services in the environment matches
            # the services specified in this set
            if (available_services := self.pro_services()) != self:
                raise InvalidUbuntuProServices(self, available_services)

        except UbuntuProClientNotFound as exc:

            # If The pro client was not found, we may be on a non Ubuntu
            # system, but if Pro services were requested, re-raise error
            if self and not self.pro_client_exists():
                raise exc
