#  Copyright 2023-2024 Canonical Ltd.
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
from __future__ import annotations

import argparse
from unittest import mock

import pytest
from craft_application.commands import base
from craft_cli import EmitterMode, emit
from typing_extensions import override


@pytest.fixture
def fake_command(app_metadata, fake_services):
    class FakeCommand(base.AppCommand):
        _run_managed = True
        name = "fake"
        help_msg = "Help!"
        overview = "It's an overview."

        @override
        def run_managed(self, parsed_args: argparse.Namespace) -> bool:
            return self._run_managed

    return FakeCommand(
        {
            "app": app_metadata,
            "services": fake_services,
        }
    )


def test_get_managed_cmd_unmanaged(fake_command):
    fake_command._run_managed = False

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


@pytest.mark.parametrize("always_load_project", [True, False])
def test_needs_project(fake_command, always_load_project):
    """`needs_project()` defaults to `always_load_project`."""
    fake_command.always_load_project = always_load_project

    assert fake_command.needs_project(argparse.Namespace()) is always_load_project


# region Tests for ExtensibleCommand
@pytest.fixture
def fake_extensible_cls():
    class FakeExtensibleCommand(base.ExtensibleCommand):
        name = "fake"
        help_msg = "A fake command"
        overview = "A fake extensible command for testing."

        def __init__(self):
            self.__run_count = 0
            super().__init__({"app": None, "services": None})

        def get_run_count(self) -> dict[str, int]:
            return {"fake": self.__run_count}

        def _run(
            self, parsed_args: argparse.Namespace, **kwargs  # noqa: ARG002
        ) -> int | None:
            self.__run_count += 1
            return self.__run_count

    return FakeExtensibleCommand


@pytest.fixture
def fake_extensible_child(fake_extensible_cls):
    class FakeChild(fake_extensible_cls):
        name = "child"

        def __init__(self):
            self.__run_count = 0
            super().__init__()

        def get_run_count(self) -> dict[str, int]:
            counts = super().get_run_count()
            counts["child"] = self.__run_count
            return counts

        def _run(
            self, parsed_args: argparse.Namespace, **kwargs  # noqa: ARG002
        ) -> int | None:
            self.__run_count += 1
            return super()._run(parsed_args)

    return FakeChild


def test_extensible_command_no_callbacks(fake_extensible_cls):
    cmd = fake_extensible_cls()

    cmd.fill_parser(argparse.ArgumentParser())
    cmd.run(argparse.Namespace())

    assert cmd.get_run_count() == {"fake": 1}


def test_extensible_command_child_no_callbacks(
    fake_extensible_cls, fake_extensible_child
):
    cmd = fake_extensible_child()

    cmd.fill_parser(argparse.ArgumentParser())

    assert cmd.get_run_count() == {"fake": 0, "child": 0}

    cmd.run(argparse.Namespace())

    assert cmd.get_run_count() == {"fake": 1, "child": 1}
    assert fake_extensible_cls.get_run_count(cmd) == {"fake": 1}


def test_extensible_command_filler(fake_extensible_cls):
    filler = mock.Mock(spec=base.ParserCallback)
    parser = argparse.ArgumentParser()
    cmd = fake_extensible_cls()

    fake_extensible_cls.register_parser_filler(filler)

    cmd.fill_parser(parser)

    filler.assert_called_once_with(cmd, parser)


def test_extensible_command_prologue(fake_extensible_cls):
    prologue = mock.Mock(spec=base.RunCallback)
    parser = argparse.ArgumentParser()
    namespace = parser.parse_args([])
    cmd = fake_extensible_cls()

    fake_extensible_cls.register_prologue(prologue)

    cmd.fill_parser(parser)
    cmd.run(namespace)

    prologue.assert_called_once_with(cmd, namespace)


def test_extensible_command_epilogue(fake_extensible_cls):
    epilogue = mock.Mock(spec=base.RunCallback)
    parser = argparse.ArgumentParser()
    namespace = parser.parse_args([])
    cmd = fake_extensible_cls()

    fake_extensible_cls.register_epilogue(epilogue)

    cmd.fill_parser(parser)
    cmd.run(namespace)
    cmd.run(namespace)

    assert epilogue.call_args_list == [
        mock.call(cmd, namespace, current_result=1),
        mock.call(cmd, namespace, current_result=2),
    ]


def test_extensible_command_parser_order(
    capsys, fake_extensible_cls, fake_extensible_child
):
    fake_extensible_cls.register_parser_filler(lambda *_: print("parent", end=","))
    fake_extensible_child.register_parser_filler(lambda *_: print("child", end=","))

    fake_extensible_child().fill_parser(argparse.ArgumentParser())

    stdout, stderr = capsys.readouterr()
    assert stdout == "parent,child,"


def test_extensible_command_prologue_order(
    capsys, fake_extensible_cls, fake_extensible_child
):
    fake_extensible_cls.register_prologue(lambda *_: print("parent", end=","))
    fake_extensible_child.register_prologue(lambda *_: print("child", end=","))
    cmd = fake_extensible_child()

    cmd.run(argparse.Namespace())

    stdout, stderr = capsys.readouterr()
    assert stdout == "parent,child,"


def test_extensible_command_epilogue_order(
    capsys, fake_extensible_cls, fake_extensible_child
):
    fake_extensible_cls.register_epilogue(lambda *_, **__: print("parent", end=","))
    fake_extensible_child.register_epilogue(lambda *_, **__: print("child", end=","))
    cmd = fake_extensible_child()

    cmd.run(argparse.Namespace())

    stdout, stderr = capsys.readouterr()
    assert stdout == "parent,child,"


# endregion
