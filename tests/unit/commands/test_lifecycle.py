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
import pathlib
from unittest import mock

import craft_parts
import pytest
from craft_application.commands.lifecycle import (
    BuildCommand,
    CleanCommand,
    OverlayCommand,
    PackCommand,
    PrimeCommand,
    PullCommand,
    StageCommand,
    _LifecyclePartsCommand,
    _LifecycleStepCommand,
    get_lifecycle_command_group,
)
from craft_cli import emit
from craft_parts import Features

PARTS_LISTS = [[], ["my-part"], ["my-part", "your-part"]]
SHELL_PARAMS = [
    ({"shell": False, "shell_after": False}, []),
    ({"shell": False, "shell_after": True}, ["--shell-after"]),
    ({"shell": True, "shell_after": False}, ["--shell"]),
]
STEP_NAMES = [step.name.lower() for step in craft_parts.Step]
MANAGED_LIFECYCLE_COMMANDS = {
    PullCommand,
    OverlayCommand,
    BuildCommand,
    StageCommand,
    PrimeCommand,
}
UNMANAGED_LIFECYCLE_COMMANDS = {CleanCommand, PackCommand}
ALL_LIFECYCLE_COMMANDS = MANAGED_LIFECYCLE_COMMANDS | UNMANAGED_LIFECYCLE_COMMANDS


def get_fake_command_class(parent_cls, managed):
    """Create a fully described fake command based on a partial class."""

    class FakeCommand(parent_cls):
        run_managed = managed
        name = "fake"
        help_msg = "help"
        overview = "overview"

    return FakeCommand


@pytest.mark.parametrize(
    ["enable_overlay", "commands"],
    [
        (True, ALL_LIFECYCLE_COMMANDS),
        (
            False,
            {
                CleanCommand,
                PullCommand,
                BuildCommand,
                StageCommand,
                PrimeCommand,
                PackCommand,
            },
        ),
    ],
)
def test_get_lifecycle_command_group(enable_overlay, commands):
    Features.reset()
    Features(enable_overlay=enable_overlay)

    actual = get_lifecycle_command_group()

    assert set(actual.commands) == commands

    Features.reset()


@pytest.mark.parametrize("parts_args", PARTS_LISTS)
def test_parts_command_fill_parser(app_metadata, parts_args):
    cls = get_fake_command_class(_LifecyclePartsCommand, managed=True)
    parser = argparse.ArgumentParser("parts_command")
    command = cls({"app": app_metadata})

    command.fill_parser(parser)

    args_dict = vars(parser.parse_args(parts_args))
    assert args_dict == {"parts": parts_args}


@pytest.mark.parametrize("parts", PARTS_LISTS)
def test_parts_command_get_managed_cmd(app_metadata, parts, emitter_verbosity):
    cls = get_fake_command_class(_LifecyclePartsCommand, managed=True)

    expected = [
        app_metadata.name,
        f"--verbosity={emitter_verbosity.name.lower()}",
        "fake",
        *parts,
    ]

    parsed_args = argparse.Namespace(parts=parts)
    command = cls({"app": app_metadata})

    actual = command.get_managed_cmd(parsed_args)

    assert actual == expected


@pytest.mark.parametrize(["shell_dict", "shell_args"], SHELL_PARAMS)
@pytest.mark.parametrize("parts_args", PARTS_LISTS)
def test_step_command_fill_parser(app_metadata, parts_args, shell_args, shell_dict):
    cls = get_fake_command_class(_LifecycleStepCommand, managed=True)
    parser = argparse.ArgumentParser("step_command")
    expected = {"parts": parts_args, **shell_dict}
    command = cls({"app": app_metadata})

    command.fill_parser(parser)

    args_dict = vars(parser.parse_args([*shell_args, *parts_args]))
    assert args_dict == expected


@pytest.mark.parametrize(["shell_params", "shell_opts"], SHELL_PARAMS)
@pytest.mark.parametrize("parts", PARTS_LISTS)
def test_step_command_get_managed_cmd(
    app_metadata, parts, emitter_verbosity, shell_params, shell_opts
):
    cls = get_fake_command_class(_LifecycleStepCommand, managed=True)

    expected = [
        app_metadata.name,
        f"--verbosity={emitter_verbosity.name.lower()}",
        "fake",
        *parts,
        *shell_opts,
    ]

    emit.set_mode(emitter_verbosity)
    parsed_args = argparse.Namespace(parts=parts, **shell_params)
    command = cls({"app": app_metadata})

    actual = command.get_managed_cmd(parsed_args)

    assert actual == expected


@pytest.mark.parametrize("step_name", STEP_NAMES)
@pytest.mark.parametrize("parts", PARTS_LISTS)
def test_step_command_run_explicit_step(app_metadata, parts, step_name):
    cls = get_fake_command_class(_LifecycleStepCommand, managed=True)

    mock_parts_lifecycle = mock.Mock()
    parsed_args = argparse.Namespace(parts=parts)
    command = cls({"app": app_metadata, "lifecycle_service": mock_parts_lifecycle})

    command.run(parsed_args=parsed_args, step_name=step_name)

    mock_parts_lifecycle.run.assert_called_once_with(
        step_name=step_name, part_names=parts
    )


@pytest.mark.parametrize("command_cls", MANAGED_LIFECYCLE_COMMANDS)
@pytest.mark.parametrize(["shell_params", "shell_opts"], SHELL_PARAMS)
@pytest.mark.parametrize("parts", PARTS_LISTS)
def test_concrete_commands_get_managed_cmd(
    app_metadata, command_cls, shell_params, shell_opts, parts, emitter_verbosity
):
    expected = [
        app_metadata.name,
        f"--verbosity={emitter_verbosity.name.lower()}",
        command_cls.name,
        *parts,
        *shell_opts,
    ]

    parsed_args = argparse.Namespace(parts=parts, **shell_params)
    command = command_cls({"app": app_metadata})

    actual = command.get_managed_cmd(parsed_args)

    assert actual == expected


@pytest.mark.parametrize("command_cls", MANAGED_LIFECYCLE_COMMANDS)
@pytest.mark.parametrize("parts", PARTS_LISTS)
def test_managed_concrete_commands_run(app_metadata, command_cls, parts):
    mock_lifecycle_service = mock.Mock()
    mock_package_service = mock.Mock()
    parsed_args = argparse.Namespace(parts=parts)
    command = command_cls(
        {
            "app": app_metadata,
            "lifecycle_service": mock_lifecycle_service,
            "package_service": mock_package_service,
        }
    )

    command.run(parsed_args)

    mock_lifecycle_service.run.assert_called_once_with(
        step_name=command.name, part_names=parts
    )


@pytest.mark.parametrize("parts", PARTS_LISTS)
def test_clean_run(app_metadata, parts, tmp_path):
    mock_lifecycle_service = mock.Mock()
    mock_package_service = mock.Mock()
    parsed_args = argparse.Namespace(parts=parts, output=tmp_path)
    command = CleanCommand(
        {
            "app": app_metadata,
            "lifecycle_service": mock_lifecycle_service,
            "package_service": mock_package_service,
        }
    )

    command.run(parsed_args)

    mock_lifecycle_service.clean.assert_called_once_with(parts)


@pytest.mark.parametrize(["shell_dict", "shell_args"], SHELL_PARAMS)
@pytest.mark.parametrize("parts_args", PARTS_LISTS)
@pytest.mark.parametrize("output_arg", [".", "/"])
def test_pack_fill_parser(app_metadata, parts_args, shell_args, shell_dict, output_arg):
    mock_lifecycle_service = mock.Mock()
    mock_package_service = mock.Mock()
    parser = argparse.ArgumentParser("step_command")
    expected = {"parts": parts_args, "output": pathlib.Path(output_arg), **shell_dict}
    command = PackCommand(
        {
            "app": app_metadata,
            "lifecycle_service": mock_lifecycle_service,
            "package_service": mock_package_service,
        }
    )

    command.fill_parser(parser)

    args_dict = vars(
        parser.parse_args([*shell_args, *parts_args, f"--output={output_arg}"])
    )
    assert args_dict == expected


@pytest.mark.parametrize(
    ["packages", "message"],
    [
        ([], "No packages created."),
        ([pathlib.Path("package.zip")], "Packed package.zip"),
        (
            [pathlib.Path("package.zip"), pathlib.Path("package.tar.zst")],
            "Packed: package.zip, package.tar.zst",
        ),
    ],
)
@pytest.mark.parametrize("parts", PARTS_LISTS)
def test_pack_run(emitter, app_metadata, parts, tmp_path, packages, message):
    mock_lifecycle_service = mock.Mock()
    mock_package_service = mock.Mock()
    mock_package_service.pack.return_value = packages
    parsed_args = argparse.Namespace(parts=parts, output=tmp_path)
    command = PackCommand(
        {
            "app": app_metadata,
            "lifecycle_service": mock_lifecycle_service,
            "package_service": mock_package_service,
        }
    )

    command.run(parsed_args)

    mock_package_service.pack.assert_called_once_with(tmp_path)
    emitter.assert_message(message)


def test_pack_run_wrong_step(app_metadata):
    parsed_args = argparse.Namespace(parts=None, output=pathlib.Path())
    command = PackCommand(
        {
            "app": app_metadata,
            "lifecycle_service": None,
            "package_service": None,
        }
    )

    with pytest.raises(RuntimeError) as exc_info:
        command.run(parsed_args, "wrong-command")

    assert exc_info.value.args[0] == "Step name wrong-command passed to pack command."
