#  This file is part of craft-application.
#
#  Copyright 2024 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Utility functions."""
import enum
import urllib.parse
from collections.abc import Iterable, Sequence
from types import MappingProxyType

from lazr.restfulclient.resource import Entry  # type: ignore[import-untyped]
from typing_extensions import Any

ARCHITECTURE_MAP = MappingProxyType({"x86_64": "amd64", "x64": "amd64", "x86": "i386"})
"""Map of alternative architecture names to Debian architectures."""


class Architecture(enum.Enum):
    """Architectures supported by Launchpad."""

    AMD64 = "amd64"
    ARM64 = "arm64"
    ARMEL = "armel"
    ARMHF = "armhf"
    I386 = "i386"
    PPC64EL = "ppc64el"
    S390X = "s390x"
    RISCV64 = "riscv64"


def getattrs(obj: object, path: Iterable[str]) -> Any:  # noqa: ANN401
    """Get an attribute from an object tree based on a path.

    :param obj: The root object of the tree.
    :param path: The getattr path.
    :returns: The resulting object.
    :raises: AttributeError if an attribute is not found.

    getattr_path(obj, "a.b.c") is equivalent to obj.a.b.c
    """
    if isinstance(path, str):
        path = path.split(".")
    path = iter(path)
    try:
        attr = next(path)
    except StopIteration:
        return obj
    try:
        inner = getattr(obj, attr)
    except AttributeError as exc:
        raise AttributeError(
            f"{obj.__class__.__name__!r} object has no attribute path {exc.name!r}",
            name=exc.name,
            obj=obj,
        ) from None
    try:
        return getattrs(inner, path)
    except AttributeError as exc:
        partial_path = f"{attr}.{exc.name}"
        raise AttributeError(
            f"{obj.__class__.__name__!r} object has no attribute path {partial_path!r}",
            name=partial_path,
            obj=obj,
        ) from None


def set_innermost_attr(
    obj: object,
    path: Sequence[str],
    value: Any,  # noqa: ANN401
) -> None:
    """Set the innermost attribute based on a path."""
    parent_path: Sequence[str] | str
    if isinstance(path, str):
        parent_path, _, attr_name = path.rpartition(".")
    else:
        parent_path = path[:-1]
        attr_name = path[-1]
    parent = getattrs(obj, parent_path) if parent_path else obj
    setattr(parent, attr_name, value)


def get_resource_type(entry: Entry) -> str:
    """Get the resource type of a Launchpad entry object as a string."""
    return str(urllib.parse.urlparse(entry.resource_type_link).fragment)


def get_person_link(person: str | Entry) -> str:
    """Get a link to a person or team.

    :param person: The person or team to link
    :returns: A Launchpad compatible link to the person.

    If the input is a string, this function assumes it is either a username or a
    link and coerces that. If it's lazr Entry, it retrieves the name and then
    converts that into a link.
    """
    if isinstance(person, Entry):
        if (resource_type := get_resource_type(person)) not in ("person", "team"):
            raise TypeError(f"Invalid resource type {resource_type!r}")
        person = person.name
    person = person.lstrip("/~").split("/", maxsplit=1)[0]
    return f"/~{person}"


def get_architecture(name: str) -> Architecture:
    """Convert a string into its canonical Launchpad architecture name.

    :param name: An architecture name that may or may not be correct.
    :returns: A Launchpad architecture name.
    :raises: ValueError if there's no way to convert the string into an architecture name.
    """
    name = name.strip().lower()
    mapped_name = ARCHITECTURE_MAP.get(name, name)
    try:
        return Architecture(mapped_name)
    except ValueError:
        raise ValueError(f"Unknown architecture {name!r}")


def get_processor(name: str) -> str:
    """Convert a string into a Launchpad processor link."""
    return f"/+processors/{get_architecture(name).value}"
