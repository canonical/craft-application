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
"""Launchpad distro_series."""

import enum

from .base import LaunchpadObject


class DistributionTypes(enum.Enum):
    """Types of distribution in Launchpad."""

    DISTRIBUTION = "distribution"


class Distribution(LaunchpadObject):
    """A distribution in Launchpad.

    https://api.launchpad.net/devel.html#distribution
    """

    _resource_types = DistributionTypes
    _attr_map = {}

    display_name: str
    domain_name: str
    name: str
    title: str


class DistroSeriesTypes(enum.Enum):
    """Types of DistroSeries in Launchpad."""

    DISTRO_SERIES = "distro_series"


class DistroSeries(LaunchpadObject):
    """A series for a specific Launchpad distribution.

    https://api.launchpad.net/devel.html#distro_series
    """

    _resource_types = DistroSeriesTypes
    _attr_map = {"display_name": "displayname"}

    display_name: str
    name: str
    title: str
    version: str
    distribution: Distribution
