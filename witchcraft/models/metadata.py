# This file is part of craft_application.
#
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
"""Witchcraft metadata models."""

from __future__ import annotations

from typing import TYPE_CHECKING

from craft_application.models import metadata

if TYPE_CHECKING:
    from .project import Component


class ComponentMetadata(metadata.BaseMetadata):
    """Component metadata."""

    summary: str | None = None
    version: str | None = None

    @classmethod
    def from_component(cls, component: Component) -> ComponentMetadata:
        """Create a ComponentMetadata model from a Component model."""
        return cls.unmarshal(component.marshal())


class Metadata(metadata.BaseMetadata):
    """Witchcraft metadata."""

    name: str
    version: str
    craft_application_version: str
    components: dict[str, ComponentMetadata] | None = None
