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
"""Handling of Ubuntu Pro Services."""

from __future__ import annotations

import json
import logging
import subprocess as sub
from enum import Flag, auto
from pathlib import Path
from typing import Any

from craft_application.errors import (
    InvalidUbuntuProServiceError,
    InvalidUbuntuProStatusError,
    UbuntuProApiError,
    UbuntuProAttachedError,
    UbuntuProClientNotFoundError,
    UbuntuProDetachedError,
)

logger = logging.getLogger(__name__)


# locations to search for pro executable
# TODO: which path will we support in long term?
PRO_CLIENT_PATHS = [
    Path("/usr/bin/ubuntu-advantage"),
    Path("/usr/bin/ua"),
    Path("/usr/bin/pro"),
]


class ValidatorOptions(Flag):
    """Options for ProServices.validate method.

    SUPPORT: Check names in ProServices set against supported services.
    AVAILABILITY: Check Ubuntu Pro is attached if ProServices set is not empty
    ATTACHMENT: Check Ubuntu Pro is attached or detached to match ProServices set.
    ENABLEMENT: Check enabled Ubuntu Pro enablement matches ProServices set.
    """

    SUPPORT = auto()
    _ATTACHED = auto()
    _DETACHED = auto()
    # TODO: remove AVAILABILITY if not needed. This flag is useful if we can manually control
    # if a managed instance is pro or not. It allows us to check if the host has
    # any pro services to support a pro build. In this case, if pro is not requested
    # the managed instance would not be attached.
    AVAILABILITY = _ATTACHED
    ATTACHMENT = _ATTACHED | _DETACHED
    ENABLEMENT = auto()
    DEFAULT = SUPPORT | ATTACHMENT | ENABLEMENT


class ProServices(set[str]):
    """Class for managing pro-services within the lifecycle."""

    # placeholder for empty sets
    empty_placeholder = "none"

    managed_mode = False

    supported_services: set[str] = {
        "esm-apps",
        "esm-infra",
        "fips",
        "fips-preview",
        "fips-updates",
    }

    # location of pro client
    pro_executable: Path | None = next(
        (path for path in PRO_CLIENT_PATHS if path.exists()), None
    )

    def __str__(self) -> str:
        """Convert to string for display to user."""
        return ", ".join(self) if self else self.empty_placeholder

    @classmethod
    def from_csv(cls, services: str) -> ProServices:
        """Create a new ProServices instance from a csv string."""
        split = [service.strip() for service in services.split(",")]
        return cls(split)

    @classmethod
    def pro_client_exists(cls) -> bool:
        """Check if Ubuntu Pro executable exists or not."""
        return cls.pro_executable is not None and cls.pro_executable.exists()

    @classmethod
    def _log_processes(cls, process: sub.CompletedProcess[str]) -> None:
        logger.error(
            "Ubuntu Pro Client Response: \n"
            f"Return Code: {process.returncode}\n"
            f"StdOut:\n{process.stdout}\n"
            f"StdErr:\n{process.stderr}\n"
        )

    @classmethod
    def _pro_api_call(cls, endpoint: str) -> dict[str, Any]:
        """Call Ubuntu Pro executable and parse response."""
        if not cls.pro_client_exists():
            raise UbuntuProClientNotFoundError(str(cls.pro_executable))

        try:
            proc = sub.run(
                [str(cls.pro_executable), "api", endpoint],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:
            raise UbuntuProApiError(
                f'An error occurred while executing "{cls.pro_executable}"'
            ) from exc

        if proc.returncode != 0:
            cls._log_processes(proc)
            raise UbuntuProApiError(
                f"The Pro Client returned a non-zero status: {proc.returncode}. "
                "See log for more details"
            )

        try:
            result = json.loads(proc.stdout)

        except json.decoder.JSONDecodeError:
            cls._log_processes(proc)
            raise UbuntuProApiError(
                "Could not parse JSON response from Ubuntu Pro client. "
                "See log for more details"
            )

        if result["result"] != "success":
            cls._log_processes(proc)
            raise UbuntuProApiError(
                "Ubuntu Pro API returned an error response. See log for more details"
            )

        # Ignore typing for this private method. The returned object is variable in type, but types are declared in the API docs:
        # https://canonical-ubuntu-pro-client.readthedocs-hosted.com/en/v32/references/api/
        return result  # type: ignore [no-any-return]

    @classmethod
    def is_pro_attached(cls) -> bool:
        """Return True if environment is attached to Ubuntu Pro."""
        response = cls._pro_api_call("u.pro.status.is_attached.v1")

        # Ignore typing here. This field's type is static according to:
        # https://canonical-ubuntu-pro-client.readthedocs-hosted.com/en/v32/references/api/#u-pro-status-is-attached-v1
        return response["data"]["attributes"]["is_attached"]  # type: ignore [no-any-return]

    @classmethod
    def _get_pro_services(cls) -> set[str]:
        """Return set of enabled Ubuntu Pro services in the environment.

        The returned set only includes services relevant to lifecycle commands.
        """
        response = cls._pro_api_call("u.pro.status.enabled_services.v1")
        enabled_services = response["data"]["attributes"]["enabled_services"]

        service_names = {service["name"] for service in enabled_services}

        # remove any services that aren't relevant to build services
        return service_names.intersection(cls.supported_services)

    @classmethod
    def get_pro_services(cls) -> ProServices:
        """Return a class of enabled Ubuntu Pro services in the environment.

        The returned set only includes services relevant to lifecycle commands.
        """
        return cls(cls._get_pro_services())

    def validate(
        self,
        options: ValidatorOptions = ValidatorOptions.DEFAULT,
    ) -> None:
        """Validate the environment against pro services specified in this ProServices instance."""
        # raise exception if any service was requested outside of build_service_scope
        if ValidatorOptions.SUPPORT in options and (
            invalid_services := self - self.supported_services
        ):
            raise InvalidUbuntuProServiceError(invalid_services)

        try:
            # first, check Ubuntu Pro status
            # Since we extend the set class, cast ourselves to bool to check if we empty. if we are not
            # empty, this implies we require pro services.

            if self.is_pro_attached() != bool(self):
                if ValidatorOptions._ATTACHED in options and self:  # type: ignore [reportPrivateUsage]
                    # Pro rock is requested but the host is not attached
                    raise UbuntuProDetachedError

                if (
                    ValidatorOptions._DETACHED in options  # type: ignore [reportPrivateUsage]
                    and not self
                    and not self.managed_mode
                ):
                    # Pro rock is not requested but the host is attached
                    raise UbuntuProAttachedError

            # second, check that the set of enabled pro services in the environment matches
            # the services specified in this set
            available_services = self._get_pro_services()
            if (
                ValidatorOptions.ENABLEMENT in options
                and str(self) != self.empty_placeholder
                and not self.issubset(available_services)
            ):
                raise InvalidUbuntuProStatusError(self)

        except UbuntuProClientNotFoundError:
            # If The pro client was not found, we may be on a non Ubuntu
            # system, but if Pro services were requested, re-raise error
            if self and not self.pro_client_exists():
                raise
