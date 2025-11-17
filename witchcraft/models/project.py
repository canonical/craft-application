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
"""Witchcraft project model."""

from craft_application import models


class Component(models.CraftBaseModel):
    """Witchcraft component definition."""

    adopt_info: str | None = None
    """The part name to adopt info from."""

    summary: str | None = None
    """A summary of the component."""

    version: str | None = None
    """The version of the component."""


class Project(models.Project):
    """Witchcraft project definition."""

    components: dict[str, Component] | None = None
