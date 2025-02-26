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

from collections.abc import Iterable
from typing import Any, NamedTuple

from pydantic import error_wrappers


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


def format_pydantic_error(loc: Iterable[str | int], message: str, validated_object : dict[str, Any] | None = None) -> str:
    """Format a single pydantic ErrorDict as a string.

    :param loc: An iterable of strings and integers determining the error location.
        Can be pulled from the "loc" field of a pydantic ErrorDict.
    :param message: A string of the error message.
        Can be pulled from the "msg" field of a pydantic ErrorDict.
    :returns: A formatted error.
    """
    line_num = None
    if validated_object is not None:
        for i,l in enumerate(loc):
            if i == len(loc) - 1 and f"__line__{l}" in validated_object:
                line_num = validated_object[f"__line__{l}"]
            elif type(validated_object) == dict and l in validated_object:
                validated_object = validated_object.get(l)
            elif type(validated_object) == list and type(l) == int:
                validated_object = validated_object[l]

    field_path = _format_pydantic_error_location(loc)
    message = _format_pydantic_error_message(message)
    field_name, location = FieldLocationTuple.from_str(field_path)
    if location != "top-level":
        location = repr(location)
    if line_num is not None:
        location += f" - line {line_num}"

    if message == "field required":
        return f"- field {field_name!r} required in {location} configuration"
    if message == "extra fields not permitted":
        return f"- extra field {field_name!r} not permitted in {location} configuration"
    if message == "the list has duplicated items":
        return f"- duplicate {field_name!r} entry not permitted in {location} configuration"
    if field_path in ("__root__", ""):
        return f"- {message}"
    return f"- {message} (in field {field_path!r}" + (f" - line {line_num})" if line_num else ")")


def format_pydantic_errors(
    errors: Iterable[error_wrappers.ErrorDict], *, file_name: str = "yaml file", validated_object: dict[str, Any] | None
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
    messages = (format_pydantic_error(error["loc"], error["msg"], validated_object) for error in errors)
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
