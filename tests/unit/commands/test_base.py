#  This file is part of craft-application.
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
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for AppCommand."""
import argparse

import pytest
from craft_application.commands import base
from craft_cli import EmitterMode, emit


@pytest.fixture()
def fake_command(app_metadata, fake_services):
    class FakeCommand(base.AppCommand):
        run_managed = True
        name = "fake"
        help_msg = "Help!"
        overview = "It's an overview."

    return FakeCommand(
        {
            "app": app_metadata,
            "services": fake_services,
        }
    )


def test_get_managed_cmd_unmanaged(fake_command):
    fake_command.run_managed = False

    with pytest.raises(RuntimeError):
        fake_command.get_managed_cmd(argparse.Namespace())


@pytest.mark.parametrize("verbosity", list(EmitterMode))
def test_get_managed_cmd(fake_command, verbosity, app_metadata):
    emit.set_mode(verbosity)

    actual = fake_command.get_managed_cmd(argparse.Namespace())

    assert actual == [
        app_metadata.name,
        f"--verbosity={verbosity.name.lower()}",
        "fake",
    ]


def test_without_config(emitter):
    """Test that a command can be initialised without a config.

    This is necessary for providing per-command help.
    """

    command = base.AppCommand(None)

    emitter.assert_trace("Not completing command configuration")
    assert not hasattr(command, "_app")
    assert not hasattr(command, "_services")
