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
"""Constants used in craft-application."""

CRAFT_DEBUG_ENV = "CRAFT_DEBUG"
"""The environment variable for enabling developer debugging."""

CRAFT_STATE_DIR_ENV = "CRAFT_STATE_DIR"
"""The environment variable for setting the state service's directory."""

BASES_ALLOW_SLASH_IN_PART_NAME = (
    "core",
    "core18",
    "core20",
    "core22",
    "core24",
    "ubuntu@16.04",
    "ubuntu@18.04",
    "ubuntu@20.04",
    "ubuntu@22.04",
    "ubuntu@24.04",
    "ubuntu@24.10",
    "ubuntu@25.04",
    "ubuntu@25.10",
    "centos@7",
    "almalinux@9",
)
"""Bases that allow the user to have a `/` character in part names.

These are essentially the list of "legacy" bases from before we banned the / character
in part names. Note that this does not apply to application-provided parts, but rather
exclusively to user-provided parts.
"""
