# This file is part of craft_application.
#
# Copyright 2024 Canonical Ltd.
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

"""Helper utilities for files."""

import io
import os
from _stat import S_IRGRP, S_IROTH, S_IRUSR

S_IRALL = S_IRUSR | S_IRGRP | S_IROTH
"""0o444 permission mask for execution permissions for everybody."""


def make_executable(fh: io.IOBase) -> None:
    """Make open file fh executable.

    Only makes the file executable for the user, group, or other if they already had read permissions.

    :param fh: An open file object.
    """
    fileno = fh.fileno()
    mode = os.fstat(fileno).st_mode
    mode_r = mode & S_IRALL
    mode_x = mode_r >> 2
    mode = mode | mode_x
    os.fchmod(fileno, mode)
