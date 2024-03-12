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
import subprocess

import craft_parts
import pytest
from craft_application.commands.lifecycle import (
    BuildCommand,
    CleanCommand,
    LifecyclePartsCommand,
    LifecycleStepCommand,
    OverlayCommand,
    PackCommand,
    PrimeCommand,
    PullCommand,
    StageCommand,
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
DEBUG_PARAMS = [
    ({"debug": False}, []),
    ({"debug": True}, ["--debug"]),
]
# --destructive-mode and --use-lxd are mutually exclusive
BUILD_ENV_COMMANDS = [
    ({"destructive_mode": False, "use_lxd": False}, []),
    ({"destructive_mode": True, "use_lxd": False}, ["--destructive-mode"]),
    ({"destructive_mode": False, "use_lxd": True}, ["--use-lxd"]),
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
        _run_managed = managed
        name = "fake"
        help_msg = "help"
        overview = "overview"

        def run_managed(self, parsed_args: argparse.Namespace) -> bool:  # noqa: ARG002
            return self._run_managed

    return FakeCommand


@pytest.mark.parametrize(
    ("enable_overlay", "commands"),
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


@pytest.mark.parametrize(("build_env_dict", "build_env_args"), BUILD_ENV_COMMANDS)
@pytest.mark.parametrize("parts_args", PARTS_LISTS)
def test_parts_command_fill_parser(
    app_metadata,
    fake_services,
    build_env_dict,
    build_env_args,
    parts_args,
):
    cls = get_fake_command_class(LifecyclePartsCommand, managed=True)
    parser = argparse.ArgumentParser("parts_command")
    command = cls({"app": app_metadata, "services": fake_services})

    command.fill_parser(parser)

    args_dict = vars(parser.parse_args([*parts_args, *build_env_args]))
    assert args_dict == {"parts": parts_args, **build_env_dict}


@pytest.mark.parametrize("parts", PARTS_LISTS)
def test_parts_command_get_managed_cmd(
    app_metadata, fake_services, parts, emitter_verbosity
):
    cls = get_fake_command_class(LifecyclePartsCommand, managed=True)

    expected = [
        app_metadata.name,
        f"--verbosity={emitter_verbosity.name.lower()}",
        "fake",
        *parts,
    ]

    parsed_args = argparse.Namespace(parts=parts)
    command = cls({"app": app_metadata, "services": fake_services})

    actual = command.get_managed_cmd(parsed_args)

    assert actual == expected


@pytest.mark.parametrize(
    ("destructive", "build_env", "expected_run_managed"),
    [
        # Destructive mode or CRAFT_BUILD_ENV=host should not run managed
        (False, "host", False),
        (True, "host", False),
        (True, "lxd", False),
        # Non-destructive mode and CRAFT_BUILD_ENV!=host should run managed
        (False, "lxd", True),
    ],
)
@pytest.mark.parametrize("parts", PARTS_LISTS)
# clean command has different logic for `run_managed()`
@pytest.mark.parametrize("command_cls", ALL_LIFECYCLE_COMMANDS - {CleanCommand})
def test_parts_command_run_managed(
    app_metadata,
    mock_services,
    destructive,
    build_env,
    expected_run_managed,
    parts,
    command_cls,
    monkeypatch,
):
    monkeypatch.setenv("CRAFT_BUILD_ENVIRONMENT", build_env)
    parsed_args = argparse.Namespace(parts=parts, destructive_mode=destructive)
    command = command_cls({"app": app_metadata, "services": mock_services})

    assert command.run_managed(parsed_args) == expected_run_managed


@pytest.mark.parametrize(("build_env_dict", "build_env_args"), BUILD_ENV_COMMANDS)
@pytest.mark.parametrize(("debug_dict", "debug_args"), DEBUG_PARAMS)
@pytest.mark.parametrize(("shell_dict", "shell_args"), SHELL_PARAMS)
@pytest.mark.parametrize("parts_args", PARTS_LISTS)
def test_step_command_fill_parser(
    app_metadata,
    fake_services,
    parts_args,
    build_env_dict,
    build_env_args,
    debug_dict,
    debug_args,
    shell_args,
    shell_dict,
):
    cls = get_fake_command_class(LifecycleStepCommand, managed=True)
    parser = argparse.ArgumentParser("step_command")
    expected = {
        "parts": parts_args,
        "platform": None,
        "build_for": None,
        **shell_dict,
        **debug_dict,
        **build_env_dict,
    }
    command = cls({"app": app_metadata, "services": fake_services})

    command.fill_parser(parser)

    args_dict = vars(
        parser.parse_args([*build_env_args, *shell_args, *debug_args, *parts_args])
    )
    assert args_dict == expected


@pytest.mark.parametrize(("shell_params", "shell_opts"), SHELL_PARAMS)
@pytest.mark.parametrize("parts", PARTS_LISTS)
def test_step_command_get_managed_cmd(
    app_metadata, fake_services, parts, emitter_verbosity, shell_params, shell_opts
):
    cls = get_fake_command_class(LifecycleStepCommand, managed=True)

    expected = [
        app_metadata.name,
        f"--verbosity={emitter_verbosity.name.lower()}",
        "fake",
        *parts,
        *shell_opts,
    ]

    emit.set_mode(emitter_verbosity)
    parsed_args = argparse.Namespace(parts=parts, **shell_params)
    command = cls({"app": app_metadata, "services": fake_services})

    actual = command.get_managed_cmd(parsed_args)

    assert actual == expected


@pytest.mark.parametrize("step_name", STEP_NAMES)
@pytest.mark.parametrize("parts", PARTS_LISTS)
def test_step_command_run_explicit_step(app_metadata, mock_services, parts, step_name):
    cls = get_fake_command_class(LifecycleStepCommand, managed=True)

    parsed_args = argparse.Namespace(parts=parts)
    command = cls({"app": app_metadata, "services": mock_services})

    command.run(parsed_args=parsed_args, step_name=step_name)

    mock_services.lifecycle.run.assert_called_once_with(
        step_name=step_name, part_names=parts
    )


@pytest.mark.parametrize("command_cls", MANAGED_LIFECYCLE_COMMANDS)
def test_step_command_failure(app_metadata, mock_services, command_cls):
    parsed_args = argparse.Namespace(parts=None)
    error_message = "Lifecycle run failed!"

    # Make lifecycle.run() raise an error.
    mock_services.lifecycle.run.side_effect = RuntimeError(error_message)
    command = command_cls(
        {
            "app": app_metadata,
            "services": mock_services,
        }
    )

    # Check that the error is propagated out
    with pytest.raises(RuntimeError, match=error_message):
        command.run(parsed_args)

    mock_services.lifecycle.run.assert_called_once_with(
        step_name=command_cls.name, part_names=None
    )


@pytest.mark.parametrize("command_cls", MANAGED_LIFECYCLE_COMMANDS)
@pytest.mark.parametrize(("shell_params", "shell_opts"), SHELL_PARAMS)
@pytest.mark.parametrize("parts", PARTS_LISTS)
def test_concrete_commands_get_managed_cmd(
    app_metadata,
    fake_services,
    command_cls,
    shell_params,
    shell_opts,
    parts,
    emitter_verbosity,
):
    expected = [
        app_metadata.name,
        f"--verbosity={emitter_verbosity.name.lower()}",
        command_cls.name,
        *parts,
        *shell_opts,
    ]

    parsed_args = argparse.Namespace(
        destructive_mode=False, parts=parts, **shell_params
    )
    command = command_cls({"app": app_metadata, "services": fake_services})

    actual = command.get_managed_cmd(parsed_args)

    assert actual == expected


@pytest.mark.parametrize("command_cls", MANAGED_LIFECYCLE_COMMANDS)
@pytest.mark.parametrize("parts", PARTS_LISTS)
def test_managed_concrete_commands_run(app_metadata, mock_services, command_cls, parts):
    parsed_args = argparse.Namespace(parts=parts)
    command = command_cls({"app": app_metadata, "services": mock_services})

    command.run(parsed_args)

    mock_services.lifecycle.run.assert_called_once_with(
        step_name=command.name, part_names=parts
    )


@pytest.mark.parametrize("parts", [("my-part",), ("my-part", "your-part")])
def test_clean_run_with_parts(app_metadata, parts, tmp_path, mock_services):
    parsed_args = argparse.Namespace(
        parts=parts, output=tmp_path, destructive_mode=False
    )
    command = CleanCommand({"app": app_metadata, "services": mock_services})

    command.run(parsed_args)

    mock_services.lifecycle.clean.assert_called_once_with(parts)
    assert not mock_services.provider.clean_instances.called


@pytest.mark.parametrize(
    ("destructive_mode", "build_env", "expected_lifecycle", "expected_provider"),
    [
        # destructive mode or CRAFT_BUILD_ENV==host should clean on host
        (False, "host", True, False),
        (True, "lxd", True, False),
        (True, "host", True, False),
        # destructive mode==False and CRAFT_BUILD_ENV!=host should clean instances
        (False, "lxd", False, True),
    ],
)
def test_clean_run_without_parts(
    app_metadata,
    tmp_path,
    mock_services,
    destructive_mode,
    build_env,
    expected_lifecycle,
    expected_provider,
    monkeypatch,
):
    monkeypatch.setenv("CRAFT_BUILD_ENVIRONMENT", build_env)
    parts = []
    parsed_args = argparse.Namespace(
        parts=parts, output=tmp_path, destructive_mode=destructive_mode
    )
    command = CleanCommand({"app": app_metadata, "services": mock_services})

    command.run(parsed_args)

    assert mock_services.lifecycle.clean.called == expected_lifecycle
    assert mock_services.provider.clean_instances.called == expected_provider


@pytest.mark.parametrize(
    ("destructive", "build_env", "parts", "expected_run_managed"),
    [
        # destructive mode or CRAFT_BUILD_ENV==host should not run managed
        (True, "lxd", [], False),
        (True, "host", [], False),
        (False, "host", [], False),
        (True, "lxd", ["part1"], False),
        (True, "host", ["part1"], False),
        (False, "host", ["part1"], False),
        (True, "lxd", ["part1", "part2"], False),
        (True, "host", ["part1", "part2"], False),
        (False, "host", ["part1", "part2"], False),
        # destructive mode==False and CRAFT_BUILD_ENV!=host: depends on "parts"
        # clean specific parts: should run managed
        (False, "lxd", ["part1"], True),
        (False, "lxd", ["part1", "part2"], True),
        # "part-less" clean: shouldn't run managed
        (False, "lxd", [], False),
    ],
)
def test_clean_run_managed(
    app_metadata,
    mock_services,
    destructive,
    build_env,
    parts,
    expected_run_managed,
    monkeypatch,
):
    monkeypatch.setenv("CRAFT_BUILD_ENVIRONMENT", build_env)
    parsed_args = argparse.Namespace(parts=parts, destructive_mode=destructive)
    command = CleanCommand({"app": app_metadata, "services": mock_services})

    assert command.run_managed(parsed_args) == expected_run_managed


@pytest.mark.parametrize(("build_env_dict", "build_env_args"), BUILD_ENV_COMMANDS)
@pytest.mark.parametrize(("debug_dict", "debug_args"), DEBUG_PARAMS)
@pytest.mark.parametrize("parts_args", PARTS_LISTS)
@pytest.mark.parametrize("output_arg", [".", "/"])
def test_pack_fill_parser(
    app_metadata,
    mock_services,
    build_env_dict,
    build_env_args,
    debug_dict,
    debug_args,
    parts_args,
    output_arg,
):
    parser = argparse.ArgumentParser("step_command")
    expected = {
        "parts": parts_args,
        "platform": None,
        "build_for": None,
        "output": pathlib.Path(output_arg),
        **debug_dict,
        **build_env_dict,
    }
    command = PackCommand({"app": app_metadata, "services": mock_services})

    command.fill_parser(parser)

    args_dict = vars(
        parser.parse_args(
            [*build_env_args, *parts_args, *debug_args, f"--output={output_arg}"]
        )
    )
    assert args_dict == expected


@pytest.mark.parametrize(
    ("packages", "message"),
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
def test_pack_run(
    emitter, mock_services, app_metadata, parts, tmp_path, packages, message
):
    mock_services.package.pack.return_value = packages
    parsed_args = argparse.Namespace(parts=parts, output=tmp_path)
    command = PackCommand(
        {
            "app": app_metadata,
            "services": mock_services,
        }
    )

    command.run(parsed_args)

    mock_services.package.pack.assert_called_once_with(
        mock_services.lifecycle.prime_dir,
        tmp_path,
    )
    emitter.assert_progress("Packing...")
    emitter.assert_progress(message, permanent=True)


def test_pack_run_wrong_step(app_metadata, fake_services):
    parsed_args = argparse.Namespace(parts=None, output=pathlib.Path())
    command = PackCommand(
        {
            "app": app_metadata,
            "services": fake_services,
        }
    )

    with pytest.raises(RuntimeError) as exc_info:
        command.run(parsed_args, step_name="wrong-command")

    assert exc_info.value.args[0] == "Step name wrong-command passed to pack command."


@pytest.fixture()
def mock_subprocess_run(mocker):
    return mocker.patch.object(subprocess, "run")


@pytest.mark.parametrize(
    ("command_cls", "expected_step"),
    [
        (PullCommand, None),
        (BuildCommand, "pull"),
        (StageCommand, "build"),
        (PrimeCommand, "stage"),
    ],
)
def test_shell(
    app_metadata,
    fake_services,
    mocker,
    mock_subprocess_run,
    command_cls,
    expected_step,
):
    parsed_args = argparse.Namespace(parts=None, shell=True)
    mock_lifecycle_run = mocker.patch.object(fake_services.lifecycle, "run")
    mocker.patch.object(
        fake_services.lifecycle.project_info, "execution_finished", return_value=True
    )
    command = command_cls(
        {
            "app": app_metadata,
            "services": fake_services,
        }
    )
    command.run(parsed_args)

    mock_lifecycle_run.assert_called_once_with(step_name=expected_step, part_names=None)
    mock_subprocess_run.assert_called_once_with(["bash"], check=False)


@pytest.mark.parametrize("command_cls", MANAGED_LIFECYCLE_COMMANDS)
def test_shell_after(
    app_metadata, fake_services, mocker, mock_subprocess_run, command_cls
):
    parsed_args = argparse.Namespace(parts=None, shell_after=True)
    mock_lifecycle_run = mocker.patch.object(fake_services.lifecycle, "run")
    mocker.patch.object(
        fake_services.lifecycle.project_info, "execution_finished", return_value=True
    )
    command = command_cls(
        {
            "app": app_metadata,
            "services": fake_services,
        }
    )
    command.run(parsed_args)

    mock_lifecycle_run.assert_called_once_with(
        step_name=command_cls.name, part_names=None
    )
    mock_subprocess_run.assert_called_once_with(["bash"], check=False)


@pytest.mark.parametrize("command_cls", MANAGED_LIFECYCLE_COMMANDS | {PackCommand})
def test_debug(app_metadata, fake_services, mocker, mock_subprocess_run, command_cls):
    parsed_args = argparse.Namespace(parts=None, debug=True)
    error_message = "Lifecycle run failed!"

    # Make lifecycle.run() raise an error.
    mocker.patch.object(
        fake_services.lifecycle, "run", side_effect=RuntimeError(error_message)
    )
    command = command_cls(
        {
            "app": app_metadata,
            "services": fake_services,
        }
    )

    with pytest.raises(RuntimeError, match=error_message):
        command.run(parsed_args)

    mock_subprocess_run.assert_called_once_with(["bash"], check=False)
