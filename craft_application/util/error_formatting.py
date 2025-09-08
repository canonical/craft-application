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
"""Helper utilities for formatting error messages."""

from __future__ import annotations

import os
import signal
import sys
from typing import TYPE_CHECKING, NamedTuple

import craft_cli
import craft_parts
import craft_platforms
import craft_providers

from craft_application import errors

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pydantic import error_wrappers

    from craft_application.application import AppMetadata


class FieldLocationTuple(NamedTuple):
    """A NamedTuple containing a field and a location."""

    field: str
    location: str = "top-level"

    @classmethod
    def from_str(cls, loc_str: str) -> FieldLocationTuple:
        """Return split field location.

        If top-level, location is returned as unquoted "top-level".
        If not top-level, location is returned as quoted location, e.g.
        (1) field1[idx].foo => 'foo', 'field1[idx]'
        (2) field2 => 'field2', top-level
        :returns: Tuple of <field name>, <location> as printable representations.
        """
        if "." not in loc_str:
            return cls(loc_str)
        location, field = loc_str.rsplit(".", maxsplit=1)
        return cls(field, location)


def format_pydantic_error(loc: Iterable[str | int], message: str) -> str:
    """Format a single pydantic ErrorDict as a string.

    :param loc: An iterable of strings and integers determining the error location.
        Can be pulled from the "loc" field of a pydantic ErrorDict.
    :param message: A string of the error message.
        Can be pulled from the "msg" field of a pydantic ErrorDict.
    :returns: A formatted error.
    """
    field_path = _format_pydantic_error_location(loc)
    message = _format_pydantic_error_message(message)
    field_name, location = FieldLocationTuple.from_str(field_path)
    if location != "top-level":
        location = repr(location)

    if message == "field required":
        return f"- field {field_name!r} required in {location} configuration"
    if message == "extra fields not permitted":
        return f"- extra field {field_name!r} not permitted in {location} configuration"
    if message == "the list has duplicated items":
        return f"- duplicate {field_name!r} entry not permitted in {location} configuration"
    if field_path in ("__root__", ""):
        return f"- {message}"
    return f"- {message} (in field {field_path!r})"


def format_pydantic_errors(
    errors: Iterable[error_wrappers.ErrorDict], *, file_name: str = "yaml file"
) -> str:
    """Format errors.

    Example 1: Single error.
    Bad snapcraft.yaml content:
    - field: <some field>
      reason: <some reason>
    Example 2: Multiple errors.
    Bad snapcraft.yaml content:
    - field: <some field>
      reason: <some reason>
    - field: <some field 2>
      reason: <some reason 2>.
    """
    messages = (format_pydantic_error(error["loc"], error["msg"]) for error in errors)
    return "\n".join((f"Bad {file_name} content:", *messages))


def _format_pydantic_error_location(loc: Iterable[str | int]) -> str:
    """Format location."""
    loc_parts: list[str] = []
    for loc_part in loc:
        if isinstance(loc_part, str):
            loc_parts.append(loc_part)
        else:
            # Integer indicates an index. Append as an index of the previous part.
            loc_parts.append(f"{loc_parts.pop()}[{loc_part}]")

    loc = ".".join(loc_parts)

    # Filter out internal __root__ detail.
    return loc.replace(".__root__", "")


def _format_pydantic_error_message(msg: str) -> str:
    """Format pydantic's error message field."""
    # Replace shorthand "str" with "string".
    msg = msg.replace("str type expected", "string type expected")
    msg = msg.removeprefix("Value error, ")
    if msg:
        msg = msg[0].lower() + msg[1:]
    return msg


def transform_runtime_error(
    app: AppMetadata, error: BaseException, *, debug_mode: bool = False
) -> craft_cli.CraftError | None:
    """Convert the many possible runtime errors into a more consistent type and appearance.

    Returns none on application usage errors, as those are handled specially.
    """
    match error:
        case craft_cli.ArgumentParsingError():
            print(error, file=sys.stderr)
            return None
        case KeyboardInterrupt():
            return_code = 128 + signal.SIGINT
            transformed = craft_cli.CraftError("Interrupted.", retcode=return_code)
        case craft_cli.CraftError():
            return error
        case craft_parts.PartsError():
            transformed = errors.PartsLifecycleError.from_parts_error(error)
            transformed.retcode = 1
        case craft_providers.ProviderError():
            transformed = craft_cli.CraftError(
                error.brief, details=error.details, resolution=error.resolution
            )
            transformed.retcode = 1
        case craft_platforms.CraftPlatformsError():
            transformed = craft_cli.CraftError(
                error.args[0],
                details=error.details,
                resolution=error.resolution,
                reportable=error.reportable,
                docs_url=error.docs_url,
                doc_slug=error.doc_slug,
                logpath_report=error.logpath_report,
                retcode=error.retcode,
            )
        case _:
            if isinstance(error, craft_platforms.CraftError):
                transformed = craft_cli.CraftError(
                    error.args[0],
                    details=error.details,
                    resolution=error.resolution,
                    docs_url=getattr(error, "docs_url", None),
                    doc_slug=getattr(error, "doc_slug", None),
                    logpath_report=getattr(error, "logpath_report", True),
                    reportable=getattr(error, "reportable", True),
                    retcode=getattr(error, "retcode", 1),
                )
            else:
                transformed = craft_cli.CraftError(
                    f"{app.name} internal error: {error!r}",
                )
                transformed.retcode = os.EX_SOFTWARE
            if debug_mode:
                raise error

    transformed.__cause__ = error
    return transformed
