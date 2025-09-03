# noqa: A005
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
"""Model for a FANCY platform. 🎩🧐."""

from craft_application.models import platforms
from craft_application.models.constraints import UniqueList


class FancyPlatform(platforms.Platform):
    """Model for a FANCY platform. 🎩🧐."""

    extensions: UniqueList[str]


class FancyPlatformsDict(platforms.GenericPlatformsDict[FancyPlatform]):
    """Model for a FANCY dictionary of platforms! 🎩🧐."""
