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

"""Unit tests for utility functions and helpers related to path handling."""

from _stat import S_IRGRP, S_IROTH, S_IRUSR, S_IWUSR, S_IXGRP, S_IXOTH, S_IXUSR

import pytest
from craft_application.util import file

USER = S_IRUSR | S_IWUSR  # 0o600
USER_GROUP = USER | S_IRGRP  # 0o640
USER_GROUP_OTHER = USER_GROUP | S_IROTH  # 0o644


@pytest.mark.parametrize(
    ("initial_permissions", "expected_permissions"),
    [
        pytest.param(USER, USER | S_IXUSR, id="user"),
        pytest.param(
            USER_GROUP,
            USER_GROUP | S_IXUSR | S_IXGRP,
            id="user-group",
        ),
        pytest.param(
            USER_GROUP_OTHER,
            USER_GROUP_OTHER | S_IXUSR | S_IXGRP | S_IXOTH,
            id="user-group-other",
        ),
    ],
)
def test_make_executable_read_bits(initial_permissions, expected_permissions, tmp_path):
    """make_executable should only operate where the read bits are set."""
    test_file = tmp_path / "test"
    test_file.touch(mode=initial_permissions)

    with test_file.open() as fd:
        file.make_executable(fd)

    # only read bits got made executable
    assert test_file.stat().st_mode & 0o777 == expected_permissions
