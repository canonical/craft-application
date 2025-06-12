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
import tempfile
import urllib.parse
from typing import TYPE_CHECKING

from craft_application.util.platforms import is_managed_mode

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


def get_managed_pack_state_path(app: AppMetadata) -> pathlib.PosixPath:
    """Get the path to the pack state file inside a build instance.

    Note that this always returns a PosixPath, as it refers to a path inside of
    a Linux-based build instance.
    """
    return pathlib.PosixPath(
        f"/tmp/{app.name}-pack.yaml"  # noqa: S108 - only applies inside managed instance.
    )


def get_filename_from_url_path(url: str) -> str:
    """Get just the filename of a URL path."""
    return pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name


def get_work_dir(project_dir: pathlib.Path) -> pathlib.Path:
    """Get the work directory to hand to craft-parts.

    :param project_dir: The directory containing the project
    :returns: The craft-parts work directory.

    When running in managed mode, this returns the managed mode work directory
    of ``/root``. Otherwise, it returns the project directory.
    """
    if is_managed_mode():
        return pathlib.Path("/root")
    return project_dir


def get_home_temporary_directory() -> pathlib.Path:
    """Create a persistent temporary directory in the home directory where Multipass has access.

    This is useful when mounting a directory to Multipass, which can't access /tmp.

    :returns: A path to a temporary directory in the home directory.
    """
    tmp_dir = tempfile.mkdtemp(suffix=".tmp-craft", dir=pathlib.Path.home())
    return pathlib.Path(tmp_dir)
