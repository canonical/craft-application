# Copyright (C) 2022,2024 Canonical Ltd
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
import os
import pathlib

import pytest


@pytest.fixture
def new_dir(tmp_path):
    """Change to a new temporary directory."""

    cwd = pathlib.Path.cwd()
    os.chdir(tmp_path)

    yield tmp_path

    os.chdir(cwd)
