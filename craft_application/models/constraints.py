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
"""Constrained pydantic types for *craft applications."""
import re

from pydantic import ConstrainedList, ConstrainedStr, StrictStr


class ProjectName(ConstrainedStr):
    """A constrained string for describing a project name.

    Project name rules:
     * Valid characters are lower-case ASCII letters, numerals and hyphens.
     * Must contain at least one letter
     * May not start or end with a hyphen
     * May not have two hyphens in a row
    """

    min_length = 1
    max_length = 40
    strict = True
    strip_whitespace = True
    regex = re.compile(r"^([a-z0-9][a-z0-9-]?)*[a-z]+([a-z0-9-]?[a-z0-9])*$")


MESSAGE_INVALID_NAME = (
    "Invalid name: Names can only use ASCII lowercase letters, numbers, and hyphens. "
    "They must have at least one letter, may not start or end with a hyphen, "
    "and may not have two hyphens in a row."
)


class ProjectTitle(StrictStr):
    """A constrained string for describing a project title."""

    min_length = 2
    max_length = 40
    strip_whitespace = True


class SummaryStr(ConstrainedStr):
    """A constrained string for a short summary of a project."""

    strip_whitespace = True
    max_length = 78


class UniqueStrList(ConstrainedList):
    """A list of strings, each of which must be unique.

    This is roughly equivalent to an ordered set of strings, but implemented with a list.
    """

    __args__ = (str,)
    item_type = str
    unique_items = True


class VersionStr(ConstrainedStr):
    """A valid version string.

    Should match snapd valid versions:
    https://github.com/snapcore/snapd/blame/a39482ead58bf06cddbc0d3ffad3c17dfcf39913/snap/validate.go#L96
    Applications may use a different set of constraints if necessary, but
    ideally they will retain this same constraint.
    """

    max_length = 32
    strip_whitespace = True
    regex = re.compile(r"^[a-zA-Z0-9](?:[a-zA-Z0-9:.+~-]*[a-zA-Z0-9+~])?$")


MESSAGE_INVALID_VERSION = (
    "Invalid version: Valid versions consist of upper- and lower-case "
    "alphanumeric characters, as well as periods, colons, plus signs, tildes, "
    "and hyphens. They cannot begin with a period, colon, plus sign, tilde, or "
    "hyphen. They cannot end with a period, colon, or hyphen."
)
