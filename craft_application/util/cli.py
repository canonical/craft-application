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
"""CLI-related utilities."""

import datetime
import warnings


def format_timestamp(dt: datetime.datetime) -> str:
    """Convert a datetime object (with or without timezone) to a string.

    The format is an ISO 8601-compliant UTC date and time stamp formatted as:

        <DATE>T<TIME>Z

    Timezone-aware datetime objects are converted to UTC. Timezone-naive ones
    are assumed to be UTC.
    """
    if dt.tzinfo is not None and dt.tzinfo.utcoffset(None) is not None:
        # timezone aware
        dtz = dt.astimezone(datetime.timezone.utc)
    else:
        # timezone naive, assume it's UTC
        dtz = dt
        warnings.warn(
            "Timezone-naive datetime used. Replace with a timezone-aware one if possible.",
            category=UserWarning,
            stacklevel=2,
        )
    return dtz.strftime("%Y-%m-%dT%H:%M:%SZ")
