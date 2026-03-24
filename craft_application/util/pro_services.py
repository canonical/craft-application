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
"""Handling of Pro services."""

from __future__ import annotations

import json
import logging
import subprocess
from enum import Flag, auto
from pathlib import Path
from typing import TYPE_CHECKING, Any

import craft_cli

from craft_application.errors import (
    InvalidUbuntuProBaseError,
    InvalidUbuntuProServiceError,
    InvalidUbuntuProStatusError,
    UbuntuProApiError,
    UbuntuProAttachedError,
    UbuntuProClientNotFoundError,
    UbuntuProDetachedError,
)

if TYPE_CHECKING:
    from craft_application import models

logger = logging.getLogger(__name__)


# check for Pro client in these paths for backwards compatibility.
_PRO_CLIENT_PATHS = [
    Path("/usr/bin/ubuntu-advantage"),
    Path("/usr/bin/ua"),
    Path("/usr/bin/pro"),
]


class _ValidatorOptions(Flag):
    """Options for ProServices.validate method.

    SUPPORT: Check names in ProServices set against supported services.
    AVAILABILITY: Check Pro is attached if ProServices are valid.
    ATTACHMENT: Check Pro is attached or detached to match ProServices set.
    ENABLEMENT: Check enabled Pro enablement matches ProServices set.
    """

    SUPPORT = auto()
    ATTACHED = auto()
    DETACHED = auto()
    ATTACHMENT = ATTACHED | DETACHED
    ENABLEMENT = auto()
    DEFAULT = SUPPORT | ATTACHMENT | ENABLEMENT
    AVAILABILITY = ATTACHED | SUPPORT


class ProServices(set[str]):
    """Class for managing Pro services within the lifecycle."""

    # placeholder for empty sets
    _empty_placeholder = "None"

    supported_services: set[str] = {
        "esm-apps",
        "esm-infra",
        "fips",
        "fips-preview",
        "fips-updates",
    }

    # location of Pro client
    _pro_executable: Path | None = next(
        (path for path in _PRO_CLIENT_PATHS if path.exists()), None
    )

    def __str__(self) -> str:
        """Convert to string for display to user."""
        services = ", ".join(sorted(self)) if self else self._empty_placeholder
        return f"<ProServices: {services}>"

    @classmethod
    def from_csv(cls, services: str) -> ProServices:
        """Create a new ProServices instance from a csv string."""
        split = [service.strip() for service in services.split(",") if service.strip()]
        return cls(split)

    @classmethod
    def _pro_client_exists(cls) -> bool:
        """Check if the Pro executable exists or not."""
        return cls._pro_executable is not None and cls._pro_executable.exists()

    @classmethod
    def _log_processes(cls, process: subprocess.CompletedProcess[str]) -> None:
        logger.error(
            "Ubuntu Pro Client Response: \n"
            f"Return Code: {process.returncode}\n"
            f"StdOut:\n{process.stdout}\n"
            f"StdErr:\n{process.stderr}\n"
        )

    @classmethod
    def _pro_api_call(cls, endpoint: str) -> dict[str, Any]:
        """Call Pro executable and parse response."""
        if not cls._pro_client_exists():
            raise UbuntuProClientNotFoundError(str(cls._pro_executable))

        try:
            proc = subprocess.run(
                [str(cls._pro_executable), "api", endpoint],
                capture_output=True,
                text=True,
                check=False,
            )
        except Exception as exc:
            raise UbuntuProApiError(
                f"An error occurred while executing {str(cls._pro_executable)!r}."
            ) from exc

        if proc.returncode != 0:
            cls._log_processes(proc)
            raise UbuntuProApiError(
                f"The Ubuntu Pro client returned a non-zero status: {proc.returncode}. "
                "See log for more details."
            )

        try:
            result = json.loads(proc.stdout)

        except json.decoder.JSONDecodeError:
            cls._log_processes(proc)
            raise UbuntuProApiError(
                "Could not parse JSON response from the Ubuntu Pro client. "
                "See log for more details."
            )

        if result.get("result") != "success":
            cls._log_processes(proc)
            raise UbuntuProApiError(
                "The Ubuntu Pro API returned an error response. See log for more details."
            )

        # Ignore typing for this private method. The returned object is variable in type, but types are declared in the API docs:
        # https://canonical-ubuntu-pro-client.readthedocs-hosted.com/en/v32/references/api/
        return result  # type: ignore [no-any-return]

    @classmethod
    def _is_pro_attached(cls) -> bool:
        """Return True if environment is attached to Pro."""
        response = cls._pro_api_call("u.pro.status.is_attached.v1")

        # Ignore typing here. This field's type is static according to:
        # https://canonical-ubuntu-pro-client.readthedocs-hosted.com/en/v32/references/api/#u-pro-status-is-attached-v1
        return response["data"]["attributes"]["is_attached"]  # type: ignore [no-any-return]

    @classmethod
    def _get_pro_services(cls) -> ProServices:
        """Return set of enabled Pro services in the environment.

        The returned set only includes services relevant to lifecycle commands.
        """
        response = cls._pro_api_call("u.pro.status.enabled_services.v1")
        enabled_services = response["data"]["attributes"]["enabled_services"]

        service_names = {service["name"] for service in enabled_services}

        # remove any services that aren't relevant to build services
        service_names = service_names.intersection(cls.supported_services)

        return cls(service_names)

    def validate_project(self, project: models.Project) -> None:
        """Ensure no unsupported interim bases are used in Pro builds."""
        invalid_bases = ["devel"]
        if bool(self):
            if project.base is not None and project.base in invalid_bases:
                raise InvalidUbuntuProBaseError("base", project.base)
            if project.build_base is not None and project.build_base in invalid_bases:
                raise InvalidUbuntuProBaseError("build-base", project.build_base)

    def _validate_environment(
        self,
        options: _ValidatorOptions = _ValidatorOptions.DEFAULT,
    ) -> None:
        """Validate the environment against Pro services specified in this ProServices instance.

        :param options: An enum of what to validate.

        :raises InvalidUbuntuProServiceError: If any unsupported services are enabled.
        :raises InvalidUbuntuProStatusError: If the incorrect services are enabled.
        :raises UbuntuProDetachedError: If Pro isn't attached and it should be.
        :raises UbuntuProAttachedError: If Pro is attached and it shouldn't be.
        :raises UbuntuProClientNotFoundError: If the Pro client can't be found.
        """
        # raise exception if any service was requested outside of build_service_scope
        if _ValidatorOptions.SUPPORT in options and (
            invalid_services := self - self.supported_services
        ):
            raise InvalidUbuntuProServiceError(invalid_services)

        try:
            # first, check Pro status
            # Since we extend the set class, cast ourselves to bool to check if we empty. if we are not
            # empty, this implies we require Pro services.
            is_pro_attached = self._is_pro_attached()

            if (
                _ValidatorOptions.ATTACHED in options
                and bool(self)
                and not is_pro_attached
            ):
                # Pro is requested but not attached
                raise UbuntuProDetachedError

            if (
                _ValidatorOptions.DETACHED in options
                and not bool(self)
                and is_pro_attached
            ):
                # Pro is not requested but attached
                raise UbuntuProAttachedError

            # second, check that the set of enabled Pro services in the environment matches
            # the services specified in this set
            if _ValidatorOptions.ENABLEMENT in options and (
                (available_services := self._get_pro_services()) != self
            ):
                raise InvalidUbuntuProStatusError(self, available_services)

        except UbuntuProClientNotFoundError:
            # If the Pro client was not found, we may be on a non Ubuntu
            # system, but if Pro services were requested, re-raise error
            if self and not self._pro_client_exists():
                raise

    def check_pro_context(self, *, run_managed: bool, is_managed: bool) -> None:
        """Validate Pro services are correctly configured for the current context.

        :param run_managed: Whether the command runs inside a managed instance.
        :param is_managed: Whether the application is currently running inside a
            managed instance.

        :raises InvalidUbuntuProStateError: If Pro isn't properly configured.
        :raises UbuntuProClientNotFoundError: If the Pro client can't be found.
        """
        # Validate requested Pro services on the host if we are running in destructive mode.
        if not run_managed and not is_managed:
            craft_cli.emit.debug(
                f"Validating requested Ubuntu Pro status on host: {self}"
            )
            self._validate_environment()
        # Validate requested Pro services running in managed mode inside a managed instance.
        elif run_managed and is_managed:
            craft_cli.emit.debug(
                f"Validating requested Ubuntu Pro status in managed instance: {self}"
            )
            self._validate_environment()
        # Validate Pro attachment and service names on the host before starting a managed instance.
        elif run_managed and not is_managed:
            craft_cli.emit.debug(
                f"Validating requested Ubuntu Pro attachment on host: {self}"
            )
            self._validate_environment(
                options=_ValidatorOptions.AVAILABILITY,
            )
        # no-op if running a non-managed command inside a managed instance
        else:
            craft_cli.emit.debug(
                "Skipping Ubuntu Pro validation: running a non-managed command "
                "inside a managed instance."
            )
