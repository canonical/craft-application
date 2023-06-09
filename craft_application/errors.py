# This file is part of craft_application.
#
# Copyright 2023 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Error classes for craft-application.

All errors inherit from craft_cli.CraftError.
"""
from __future__ import annotations

from typing import TypeVar

import craft_parts
import pydantic
from craft_cli import CraftError

from craft_application.util.error_formatting import format_pydantic_errors

_ErrType = TypeVar("_ErrType", bound=CraftError)


class ProjectFileMissingError(CraftError, FileNotFoundError):
    """Error finding project file."""


class CraftValidationError(CraftError):
    """Error validating project yaml."""

    @classmethod
    def from_pydantic(
        cls: type[_ErrType],
        error: pydantic.ValidationError,
        *,
        file_name: str = "yaml file",
        **kwargs: str | bool | int,
    ) -> _ErrType:
        """Convert this error from a pydantic ValidationError.

        :param error: The pydantic error to convert
        :param file_name: An optional file name of the malformed yaml file
        :param kwargs: additional keyword arguments get passed to CraftError
        """
        message = format_pydantic_errors(error.errors(), file_name=file_name)
        return cls(message, **kwargs)  # type: ignore[arg-type]


class PartsLifecycleError(CraftError):
    """Error during parts processing."""

    @classmethod
    def from_parts_error(cls: type[_ErrType], err: craft_parts.PartsError) -> _ErrType:
        """Shortcut to create a PartsLifecycleError from a PartsError."""
        return cls(message=err.brief, details=err.details, resolution=err.resolution)

    @classmethod
    def from_os_error(cls: type[_ErrType], err: OSError) -> _ErrType:
        """Create a PartsLifecycleError from an OSError."""
        if err.filename:
            message = f"{err.filename}: {err.strerror}"
        else:
            message = err.strerror
        details = err.__class__.__name__
        if err.filename:
            details += f": filename: {err.filename!r}"
        if err.filename2:
            details += f", filename2: {err.filename2!r}"
        return cls(message, details=details)
