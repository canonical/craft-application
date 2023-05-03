#  This file is part of craft_application.
#
#  Copyright 2023 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License along
#  with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Types used in craft_application projects."""
import re
from typing import Dict, List, Literal, Union

from pydantic import ConstrainedList, ConstrainedStr


class ProjectBaseStr(ConstrainedStr):
    """A constrained string to describe a project base."""

    min_length = 2
    strip_whitespace = True
    to_lower = True


class ProjectName(ConstrainedStr):
    """A constrained string for describing a project name."""

    strip_whitespace = True
    to_lower = True
    min_length = 1
    max_length = 40
    # Project name rules:
    # * Valid characters are lower-case ASCII letters, numerals and hyphens.
    # * Must contain at least one letter
    # * May not start or end with a hyphen
    # * May not have two hyphens in a row
    # The following regular expression has been lovingly crafted and
    # thoroughly tested to meet these rules.
    regex = re.compile(r"^([a-z0-9][a-z0-9-]?)?[a-z]+([a-z0-9-]?[a-z0-9])*$")


class ProjectTitle(ConstrainedStr):
    """A constrained string for describing a project title."""

    min_length = 2
    max_length = 40
    strip_whitespace = True


class SummaryStr(ConstrainedStr):
    """A constrained string for a short summary of a project."""

    strip_whitespace = True
    max_length = 78


class UniqueStrList(ConstrainedList):
    """A list of strings, each of which must be unique."""

    __args__ = (str,)
    item_type = str
    unique_items = True


class VersionStr(ConstrainedStr):
    """A valid version string."""

    max_length = 32
    strict = True
    strip_whitespace = True
    regex = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9:.+~-]*[a-zA-Z0-9+~])?$")


PlatformDict = Dict[Literal["build-on", "build-for"], Union[str, List[str]]]
