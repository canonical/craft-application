# This file is part of craft-application.
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
"""Integration tests for lifecycle commands."""

import os
import re

import freezegun
import pytest
from craft_application.application import Application


@pytest.mark.usefixtures("fake_process")  # Ensure we don't spin up a container.
@freezegun.freeze_time("2305-07-13")  # None of our current bases will be supported.
@pytest.mark.parametrize("command", ["pull", "build", "stage", "pack"])
def test_unsupported_base_error(
    app: Application,
    capsys,
    monkeypatch,
    command: str,
):
    """Initialise a project."""
    monkeypatch.setattr("sys.argv", ["testcraft", command])

    return_code = app.run()
    _, stderr = capsys.readouterr()

    assert return_code == os.EX_DATAERR
    assert re.match(
        rf"Cannot {command} artifact. (Build b|B)ase '[a-z]+@\d+\.\d+' has reached end-of-life.",
        stderr,
    )
