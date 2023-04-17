# Copyright 2023 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Error classes for craft-application.

All errors should inherit from CraftError.
"""
from typing import Iterable, Optional

from craft_cli import CraftError
from craft_parts import PartsError


class ProjectFileMissingError(CraftError):
    """Error finding project file."""


class ProjectValidationError(CraftError):
    """Error validating project yaml."""


class PartsLifecycleError(CraftError):
    """Error during parts processing."""

    @staticmethod
    def from_parts_error(err: PartsError) -> "PartsLifecycleError":
        """Shortcut to create a PartsLifecycleError from a PartsError."""
        return PartsLifecycleError(
            message=err.brief, details=err.details, resolution=err.resolution
        )


class CraftEnvironmentError(CraftError):
    """An environment variable contains an invalid value."""

    def __init__(
        self,
        variable: str,
        value: str,
        *,
        docs_url: Optional[str] = None,
        valid_values: Optional[Iterable[str]] = None,
    ) -> None:
        details = f"Value could not be parsed: {value}"
        if valid_values is not None:
            details += "\nValid values: "
            details += ", ".join(valid_values)
        super().__init__(
            message=f"Invalid value in environment variable {variable}",
            details=details,
            resolution="Unset variable or fix value.",
            docs_url=docs_url,
            logpath_report=False,
            reportable=False,
            retcode=2,
        )
