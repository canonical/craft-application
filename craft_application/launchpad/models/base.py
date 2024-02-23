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
"""Base LaunchpadObject."""
# This file relies heavily on dynamic features from launchpadlib that cause pyright
# to complain a lot. As such, we're disabling several pyright checkers for this file
# since in this case they generate more noise than utility.
# pyright: reportUnknownMemberType=false
# pyright: reportUnknownVariableType=false
# pyright: reportUnknownArgumentType=false
# pyright: reportOptionalMemberAccess=false
# pyright: reportAttributeAccessIssue=false
# pyright: reportOptionalCall=false
# pyright: reportOptionalIterable=false
# pyright: reportOptionalSubscript=false
# pyright: reportIndexIssue=false
from __future__ import annotations

import enum
from collections.abc import Mapping
from typing import TYPE_CHECKING

import lazr.restfulclient.errors  # type: ignore[import-untyped]
from lazr.restfulclient.resource import Entry  # type: ignore[import-untyped]
from typing_extensions import Any

from .. import errors, util

if TYPE_CHECKING:
    from ..launchpad import Launchpad


class InformationType(enum.Enum):
    """Type of information."""

    PUBLIC = "Public"
    PUBLIC_SECURITY = "Public Security"
    PRIVATE = "Private"
    PRIVATE_SECURITY = "Private Security"
    PROPRIETARY = "Proprietary"
    EMBARGOED = "Embargoed"


class Pocket(enum.Enum):
    """An Ubuntu archive pocket."""

    RELEASE = "Release"
    SECURITY = "Security"
    UPDATES = "Updates"
    PROPOSED = "Proposed"
    BACKPORTS = "Backports"


class LaunchpadObject:
    """A generic Launchpad object."""

    _resource_types: enum.EnumMeta
    _attr_map: Mapping[str, str] = {}
    """Mapping of attributes for this object to their paths in Launchpad."""

    def __init__(self, lp: Launchpad, lp_obj: Entry) -> None:
        self._lp = lp

        if not isinstance(
            lp_obj, Entry
        ):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError(
                f"Cannot use type {lp_obj.__class__.__name__} for launchpad entries."
            )

        self._obj = lp_obj
        resource_type = util.get_resource_type(lp_obj)

        try:
            self._resource_types(resource_type)
        except ValueError:
            raise TypeError(
                f"Launchpadlib entry not a valid resource type for {self.__class__.__name__}. "
                f"type: {resource_type!r}, "
                f"valid: {[t.value for t in self._resource_types]}",  # type: ignore[var-annotated]
            ) from None

    def delete(self) -> None:
        """Delete this object from Launchpad."""
        try:
            self._obj.lp_delete()
        except lazr.restfulclient.errors.ResponseError as exc:
            raise errors.LaunchpadError("Object could not be deleted") from exc

    @property
    def _resource_type(self) -> str:
        """The resource type of the Launchpad entry."""
        return util.get_resource_type(self._obj)

    def __dir__(self) -> list[str]:
        """Get the attributes of this object, including Launchpad attrs and entries."""
        return sorted(
            {
                *super().__dir__(),
                *util.get_annotations(self.__class__).keys(),
                *self._attr_map.keys(),
                *self.__dict__.keys(),
                *self._obj.lp_attributes,
            }
        )

    def __getattr__(self, item: str) -> Any:  # noqa: ANN401
        annotations: dict[str, type] = util.get_annotations(self.__class__)
        if item in self._attr_map:
            lp_obj = util.getattrs(self._obj, self._attr_map[item])
        elif item in (*annotations, *self._obj.lp_attributes):
            lp_obj = getattr(self._obj, item)
        elif item in self._obj.lp_collections:
            raise NotImplementedError("Cannot yet return collections")
        elif item in self._obj.lp_entries and item not in annotations:
            raise NotImplementedError("Cannot get this item type.")
        else:
            raise AttributeError(
                f"{self.__class__.__name__!r} has no attribute {item!r}"
            )

        if item in annotations:
            cls = annotations[item]
            if isinstance(cls, type) and issubclass(cls, LaunchpadObject):
                return cls(self._lp, lp_obj)
            # We expect that this class can take the object.
            return cls(lp_obj)  # type: ignore[call-arg]
        return lp_obj

    def __setattr__(self, key: str, value: Any) -> None:  # noqa: ANN401
        if key in ("_lp", "_obj"):
            self.__dict__[key] = value
            return
        annotations = util.get_annotations(self.__class__)
        if key in annotations:
            attr_path = self._attr_map.get(key, default=key)
            util.set_innermost_attr(self._obj, attr_path, value)
        elif key in self._attr_map:
            util.set_innermost_attr(self._obj, self._attr_map[key], value)
        elif key in (
            *self._obj.lp_attributes,
            *self._obj.lp_entries,
            *self._obj.lp_collections,
        ):
            setattr(self._obj, key, value)
        else:
            raise AttributeError(
                f"{self.__class__.__name__!r} has no attribute {key!r}",
            )

    def __repr__(self) -> str:
        """Get a machine-readable string of this Launchpad object."""
        return f"{self.__class__.__name__}(lp={self._lp!r}, lp_obj={self._obj!r})"

    def get_entry(self, item: str | None = None) -> Entry:
        """Get the launchpadlib Entry object for an item.

        :param item: The name of the entry to get, or None to get this object's entry.
        :returns: The Entry requested.

        This method essentially acts as a bail-out to directly access launchpadlib.
        If you use it, please file an issue with your use case.
        """
        if item is None:
            return self._obj
        if item in self._obj.lp_entries:
            return getattr(self._obj, item)
        raise ValueError(f"Entry type {self.resource_type!r} has no entry {item!r}")

    def lp_refresh(self) -> None:
        """Refresh the underlying Launchpad object."""
        self._obj.lp_refresh()
