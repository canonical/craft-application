# This file is part of craft_application.
#
# Copyright 2023-2024 Canonical Ltd.
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
"""Utility functions and helpers related to path handling."""
from __future__ import annotations

import pathlib
import urllib.parse
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from craft_application import AppMetadata


def get_managed_logpath(app: AppMetadata) -> pathlib.PosixPath:
    """Get the path to the logfile inside a build instance.

    Note that this always returns a PosixPath, as it refers to a path inside of
    a Linux-based build instance.
    """
    return pathlib.PosixPath(
        f"/tmp/{app.name}.log"  # noqa: S108 - only applies inside managed instance.
    )


def get_filename_from_url_path(url: str) -> str:
    """Get just the filename of a URL path."""
    return pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name
