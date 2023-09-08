# This file is part of craft-application.
#
# Copyright 2023 Canonical Ltd.
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
"""Tests for lifecycle commands."""
import argparse

import pytest
from craft_application.commands.other import VersionCommand, get_other_command_group

OTHER_COMMANDS = {
    VersionCommand,
}


@pytest.mark.parametrize("commands", [OTHER_COMMANDS])
def test_get_other_command_group(commands):
    actual = get_other_command_group()

    assert set(actual.commands) == commands


def test_version_run(app_metadata, tmp_path, mock_services, emitter):
    parsed_args = argparse.Namespace(output=tmp_path)
    command = VersionCommand({"app": app_metadata, "services": mock_services})
    command.run(parsed_args)

    assert emitter.assert_message("testcraft 3.14159")
