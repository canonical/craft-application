# This file is part of craft-application.
#
# Copyright 2023-2024 Canonical Ltd.
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
import re
import subprocess
from unittest import mock

import craft_cli
import craft_parts
import craft_platforms
import pytest
import pytest_mock
from craft_application import errors, models
from craft_application.application import AppMetadata
from craft_application.commands.base import AppCommand
from craft_application.commands.lifecycle import (
    BuildCommand,
    CleanCommand,
    LifecycleCommand,
    LifecyclePartsCommand,
    OverlayCommand,
    PackCommand,
    PrimeCommand,
    PullCommand,
    StageCommand,
    TestCommand,
    get_lifecycle_command_group,
)
from craft_application.services import LifecycleService
from craft_application.services.service_factory import ServiceFactory
from craft_parts import Features

pytestmark = [pytest.mark.usefixtures("fake_project_file")]

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
MANAGED_LIFECYCLE_COMMANDS = (
    PullCommand,
    OverlayCommand,
    BuildCommand,
    StageCommand,
    PrimeCommand,
)
UNMANAGED_LIFECYCLE_COMMANDS = (CleanCommand, PackCommand)
ALL_LIFECYCLE_COMMANDS = MANAGED_LIFECYCLE_COMMANDS + UNMANAGED_LIFECYCLE_COMMANDS
NON_CLEAN_COMMANDS = (*MANAGED_LIFECYCLE_COMMANDS, PackCommand)


def get_fake_command_class(parent_cls, managed):
    """Create a fully described fake command based on a partial class."""

    class FakeCommand(parent_cls):
        _run_managed = managed
        name = "fake"
        help_msg = "help"
        overview = "overview"

        def run_managed(self, parsed_args: argparse.Namespace) -> bool:
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

    assert set(actual.commands) == set(commands)

    Features.reset()


@pytest.mark.parametrize(("build_env_dict", "build_env_args"), BUILD_ENV_COMMANDS)
@pytest.mark.parametrize(("debug_dict", "debug_args"), DEBUG_PARAMS)
@pytest.mark.parametrize(("shell_dict", "shell_args"), SHELL_PARAMS)
def test_lifecycle_command_fill_parser(
    default_app_metadata,
    fake_services,
    build_env_dict,
    build_env_args,
    debug_dict,
    debug_args,
    shell_dict,
    shell_args,
):
    cls = get_fake_command_class(LifecycleCommand, managed=True)
    parser = argparse.ArgumentParser("parts_command")
    command = cls({"app": default_app_metadata, "services": fake_services})
    expected = {
        "platform": None,
        "build_for": None,
        **shell_dict,
        **debug_dict,
        **build_env_dict,
    }

    command.fill_parser(parser)

    args_dict = vars(parser.parse_args([*build_env_args, *debug_args, *shell_args]))
    assert args_dict == expected


@pytest.mark.parametrize(
    ("destructive", "managed", "build_env", "expected"),
    [
        pytest.param(False, False, "", True, id="managed-outer"),
        pytest.param(False, True, "", False, id="managed-inner"),
        pytest.param(True, False, "", False, id="destructive"),
        pytest.param(False, False, "host", False, id="build-on-host"),
        pytest.param(False, False, "something else", True, id="bad-build-env"),
        pytest.param(True, True, "host", False, id="xmas"),
    ],
)
def test_use_provider(
    mocker: pytest_mock.MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    app_metadata: AppMetadata,
    fake_services: ServiceFactory,
    destructive: bool,
    managed: bool,
    build_env: str,
    expected: bool,
):
    cls = get_fake_command_class(LifecycleCommand, managed=False)
    command = cls({"app": app_metadata, "services": fake_services})

    parsed_args = argparse.Namespace(destructive_mode=destructive)
    mocker.patch("craft_application.util.is_managed_mode", return_value=managed)
    monkeypatch.setenv("CRAFT_BUILD_ENVIRONMENT", build_env)

    assert command._use_provider(parsed_args) == expected


def test_run_sets_platform_arg(
    mocker: pytest_mock.MockerFixture,
    app_metadata: AppMetadata,
    fake_services: ServiceFactory,
    fake_platform: str,
):
    build_planner = fake_services.get("build_plan")
    cls = get_fake_command_class(LifecycleCommand, managed=False)
    command = cls({"app": app_metadata, "services": fake_services})

    mocker.patch.object(command, "_use_provider", return_value=False)
    mocker.patch.object(command, "_run_lifecycle")

    parsed_args = argparse.Namespace(platform=fake_platform)

    command.run(parsed_args)

    assert build_planner._BuildPlanService__platforms == [fake_platform]  # type: ignore[reportAttributeAccessIssue]


def test_run_sets_platform_from_env(
    mocker: pytest_mock.MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    app_metadata: AppMetadata,
    fake_services: ServiceFactory,
    fake_platform: str,
):
    build_planner = fake_services.get("build_plan")
    cls = get_fake_command_class(LifecycleCommand, managed=False)
    command = cls({"app": app_metadata, "services": fake_services})

    mocker.patch.object(command, "_use_provider", return_value=False)
    mocker.patch.object(command, "_run_lifecycle")
    monkeypatch.setenv("CRAFT_PLATFORM", fake_platform)

    parsed_args = argparse.Namespace(platform=None)

    command.run(parsed_args)

    assert build_planner._BuildPlanService__platforms == [fake_platform]  # type: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize(
    "arch", [*(arch.value for arch in craft_platforms.DebianArchitecture), "all"]
)
def test_run_sets_build_for_arg(
    mocker: pytest_mock.MockerFixture,
    app_metadata: AppMetadata,
    fake_services: ServiceFactory,
    arch: str,
):
    build_planner = fake_services.get("build_plan")
    cls = get_fake_command_class(LifecycleCommand, managed=False)
    command = cls({"app": app_metadata, "services": fake_services})

    mocker.patch.object(command, "_use_provider", return_value=False)
    mocker.patch.object(command, "_run_lifecycle")

    parsed_args = argparse.Namespace(build_for=arch)

    command.run(parsed_args)

    assert build_planner._BuildPlanService__build_for == [arch]  # type: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize(
    "arch", [*(arch.value for arch in craft_platforms.DebianArchitecture), "all"]
)
def test_run_sets_build_for_from_env(
    mocker: pytest_mock.MockerFixture,
    monkeypatch: pytest.MonkeyPatch,
    app_metadata: AppMetadata,
    fake_services: ServiceFactory,
    arch: str,
):
    build_planner = fake_services.get("build_plan")
    cls = get_fake_command_class(LifecycleCommand, managed=False)
    command = cls({"app": app_metadata, "services": fake_services})

    mocker.patch.object(command, "_use_provider", return_value=False)
    mocker.patch.object(command, "_run_lifecycle")
    monkeypatch.setenv("CRAFT_BUILD_FOR", arch)

    parsed_args = argparse.Namespace()

    command.run(parsed_args)

    assert build_planner._BuildPlanService__build_for == [arch]  # type: ignore[reportAttributeAccessIssue]


@pytest.mark.parametrize("fetch", [False, True])
def test_run_manager_for_build_plan(
    mocker: pytest_mock.MockerFixture,
    app_metadata: AppMetadata,
    fake_services: ServiceFactory,
    fetch: bool,
):
    build = craft_platforms.BuildInfo(
        platform="Tall",
        build_on=craft_platforms.DebianArchitecture.PPC64EL,
        build_for=craft_platforms.DebianArchitecture.RISCV64,
        build_base=craft_platforms.DistroBase("distro", "series"),
    )
    mock_run_managed = mocker.patch.object(fake_services.get("provider"), "run_managed")
    mocker.patch.object(fake_services.get("build_plan"), "plan", return_value=[build])
    cls = get_fake_command_class(LifecycleCommand, managed=False)

    command = cls({"app": app_metadata, "services": fake_services})
    command._run_manager_for_build_plan(fetch)

    mock_run_managed.assert_called_once_with(build, fetch)


@pytest.mark.parametrize(("build_env_dict", "build_env_args"), BUILD_ENV_COMMANDS)
@pytest.mark.parametrize(("debug_dict", "debug_args"), DEBUG_PARAMS)
@pytest.mark.parametrize(("shell_dict", "shell_args"), SHELL_PARAMS)
@pytest.mark.parametrize("parts_args", PARTS_LISTS)
def test_step_command_fill_parser(
    default_app_metadata,
    fake_services,
    parts_args,
    build_env_dict,
    build_env_args,
    debug_dict,
    debug_args,
    shell_args,
    shell_dict,
):
    cls = get_fake_command_class(LifecyclePartsCommand, managed=True)
    parser = argparse.ArgumentParser("step_command")
    expected = {
        "parts": parts_args,
        "platform": None,
        "build_for": None,
        **shell_dict,
        **debug_dict,
        **build_env_dict,
    }
    command = cls({"app": default_app_metadata, "services": fake_services})

    command.fill_parser(parser)

    args_dict = vars(
        parser.parse_args([*build_env_args, *shell_args, *debug_args, *parts_args])
    )
    assert args_dict == expected


@pytest.mark.parametrize("step_name", STEP_NAMES)
@pytest.mark.parametrize("parts", PARTS_LISTS)
@pytest.mark.usefixtures("managed_mode")
def test_step_command_run_explicit_step(app_metadata, mock_services, parts, step_name):
    cls = get_fake_command_class(LifecyclePartsCommand, managed=True)
    mock_services.get("project").configure(platform=None, build_for=None)

    parsed_args = argparse.Namespace(destructive_mode=False, parts=parts)
    command = cls({"app": app_metadata, "services": mock_services})

    command.run(parsed_args=parsed_args, step_name=step_name)

    mock_services.lifecycle.run.assert_called_once_with(
        step_name=step_name, part_names=parts
    )


@pytest.mark.parametrize("command_cls", MANAGED_LIFECYCLE_COMMANDS)
def test_step_command_failure(app_metadata, mock_services, command_cls):
    mock_services.get("project").configure(platform=None, build_for=None)
    parsed_args = argparse.Namespace(destructive_mode=True, parts=None)
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
@pytest.mark.parametrize("parts", PARTS_LISTS)
@pytest.mark.usefixtures("managed_mode")
def test_managed_concrete_commands_run(app_metadata, mock_services, command_cls, parts):
    parsed_args = argparse.Namespace(destructive_mode=False, parts=parts)
    mock_services.get("project").configure(platform=None, build_for=None)
    command = command_cls({"app": app_metadata, "services": mock_services})

    command.run(parsed_args)

    mock_services.lifecycle.run.assert_called_once_with(
        step_name=command.name, part_names=parts
    )


@pytest.mark.parametrize("parts", [("my-part",), ("my-part", "your-part")])
@pytest.mark.usefixtures("managed_mode")
def test_clean_run_with_parts_managed(app_metadata, parts, tmp_path, mock_services):
    parsed_args = argparse.Namespace(
        parts=parts, output=tmp_path, destructive_mode=False
    )
    command = CleanCommand({"app": app_metadata, "services": mock_services})

    command.run(parsed_args)

    mock_services.lifecycle.clean.assert_called_once_with(parts)
    assert not mock_services.provider.clean_instances.called


@pytest.mark.parametrize("parts", [("my-part",), ("my-part", "your-part")])
def test_clean_run_with_parts_unmanaged(app_metadata, parts, tmp_path, mock_services):
    parsed_args = argparse.Namespace(
        parts=parts, output=tmp_path, destructive_mode=False
    )
    command = CleanCommand({"app": app_metadata, "services": mock_services})
    command._run_manager_for_build_plan = mock.Mock()

    command.run(parsed_args)

    assert not mock_services.get("provider").clean_instances.called
    command._run_manager_for_build_plan.assert_called_once_with(
        fetch_service_policy=None
    )


@pytest.mark.parametrize("parts", [("my-part",), ("my-part", "your-part")])
def test_clean_run_with_parts_destructive(app_metadata, parts, tmp_path, mock_services):
    parsed_args = argparse.Namespace(
        parts=parts, output=tmp_path, destructive_mode=True
    )
    command = CleanCommand({"app": app_metadata, "services": mock_services})
    command._run_manager_for_build_plan = mock.Mock()

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
    mock_services.get("config").get.return_value = build_env
    parts = []
    parsed_args = argparse.Namespace(
        parts=parts, output=tmp_path, destructive_mode=destructive_mode
    )
    command = CleanCommand({"app": app_metadata, "services": mock_services})

    command.run(parsed_args)

    assert mock_services.get("lifecycle").clean.called == expected_lifecycle
    assert mock_services.provider.clean_instances.called == expected_provider


@pytest.mark.parametrize(("build_env_dict", "build_env_args"), BUILD_ENV_COMMANDS)
@pytest.mark.parametrize(("shell_dict", "shell_args"), SHELL_PARAMS)
@pytest.mark.parametrize(("debug_dict", "debug_args"), DEBUG_PARAMS)
@pytest.mark.parametrize("output_arg", [".", "/"])
def test_pack_fill_parser(
    app_metadata,
    mock_services,
    build_env_dict,
    build_env_args,
    shell_dict,
    shell_args,
    debug_dict,
    debug_args,
    output_arg,
):
    parser = argparse.ArgumentParser("step_command")
    expected = {
        "platform": None,
        "build_for": None,
        "output": pathlib.Path(output_arg),
        "fetch_service_policy": None,
        # This is here because app_metadata turns on checking unsupported bases.
        "ignore": [],
        **shell_dict,
        **debug_dict,
        **build_env_dict,
    }
    command = PackCommand({"app": app_metadata, "services": mock_services})

    command.fill_parser(parser)

    args_dict = vars(
        parser.parse_args(
            [*build_env_args, *shell_args, *debug_args, f"--output={output_arg}"]
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
    mocker, emitter, mock_services, app_metadata, parts, tmp_path, packages, message
):
    mock_services.package.pack.return_value = packages
    mock_services.get("project").configure(platform=None, build_for=None)
    parsed_args = argparse.Namespace(
        destructive_mode=True, parts=parts, output=tmp_path, fetch_service_policy=None
    )

    command = PackCommand(
        {
            "app": app_metadata,
            "services": mock_services,
        }
    )
    mocker.patch.object(command._services.lifecycle.project_info, "work_dir", tmp_path)
    command._services.package.resource_map = {p.stem: p for p in packages[1:]} or None  # pyright: ignore[reportAttributeAccessIssue]

    command.run(parsed_args)

    mock_services.package.pack.assert_called_once_with(
        mock_services.lifecycle.prime_dir,
        tmp_path,
    )
    emitter.assert_progress("Packing...")
    emitter.assert_progress(message, permanent=True)


@pytest.mark.parametrize(
    ("fetch_service_policy", "expect_create_called"),
    [("strict", True), ("permissive", True), (None, False)],
)
def test_pack_fetch_manifest(
    mocker,
    mock_services,
    app_metadata,
    tmp_path,
    fetch_service_policy,
    expect_create_called,
):
    packages = [pathlib.Path("package.zip")]
    mock_services.package.pack.return_value = packages
    mock_services.get("project").configure(platform=None, build_for=None)
    parsed_args = argparse.Namespace(
        destructive_mode=True,
        output=tmp_path,
        fetch_service_policy=fetch_service_policy,
    )
    command = PackCommand(
        {
            "app": app_metadata,
            "services": mock_services,
        }
    )
    mocker.patch.object(command._services.lifecycle.project_info, "work_dir", tmp_path)

    command.run(parsed_args)

    mock_services.package.pack.assert_called_once_with(
        mock_services.lifecycle.prime_dir,
        tmp_path,
    )
    assert mock_services.fetch.create_project_manifest.called == expect_create_called


@pytest.mark.usefixtures("destructive_mode")
def test_pack_run_wrong_step(app_metadata, fake_services):
    parsed_args = argparse.Namespace(
        destructive_mode=False, parts=None, output=pathlib.Path()
    )
    command = PackCommand(
        {
            "app": app_metadata,
            "services": fake_services,
        }
    )

    with pytest.raises(RuntimeError) as exc_info:
        command.run(parsed_args, step_name="wrong-command")

    assert exc_info.value.args[0] == "Step name wrong-command passed to pack command."


@pytest.fixture
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
    parsed_args = argparse.Namespace(destructive_mode=True, parts=None, shell=True)
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


def test_shell_pack(
    app_metadata,
    fake_services,
    mocker,
    mock_subprocess_run,
):
    parsed_args = argparse.Namespace(destructive_mode=True, shell=True)
    mock_lifecycle_run = mocker.patch.object(fake_services.lifecycle, "run")
    mock_pack = mocker.patch.object(fake_services.package, "pack")
    mocker.patch.object(
        fake_services.lifecycle.project_info, "execution_finished", return_value=True
    )
    command = PackCommand(
        {
            "app": app_metadata,
            "services": fake_services,
        }
    )
    command.run(parsed_args)

    # Must run the lifecycle
    mock_lifecycle_run.assert_called_once_with(step_name="prime")

    # Must call the shell instead of packing
    mock_subprocess_run.assert_called_once_with(["bash"], check=False)
    assert not mock_pack.called


@pytest.mark.parametrize("command_cls", MANAGED_LIFECYCLE_COMMANDS)
def test_shell_after(
    app_metadata, fake_services, mocker, mock_subprocess_run, command_cls
):
    parsed_args = argparse.Namespace(
        destructive_mode=True, parts=None, shell_after=True
    )
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


def test_shell_after_pack(
    app_metadata,
    fake_services,
    mocker,
    mock_subprocess_run,
):
    parsed_args = argparse.Namespace(
        destructive_mode=True,
        shell_after=True,
        output=pathlib.Path(),
        fetch_service_policy=None,
    )
    mock_lifecycle_run = mocker.patch.object(fake_services.lifecycle, "run")
    mock_pack = mocker.patch.object(fake_services.package, "pack")
    mocker.patch("craft_application.services.package.PackageService.write_state")
    mocker.patch.object(
        fake_services.lifecycle.project_info, "execution_finished", return_value=True
    )
    command = PackCommand(
        {
            "app": app_metadata,
            "services": fake_services,
        }
    )
    command.run(parsed_args)

    # Must run the lifecycle
    mock_lifecycle_run.assert_called_once_with(step_name="prime")
    # Must pack, and then shell
    mock_pack.assert_called_once_with(fake_services.lifecycle.prime_dir, pathlib.Path())
    mock_subprocess_run.assert_called_once_with(["bash"], check=False)


class FakeError(craft_platforms.CraftPlatformsError):
    """A fake error to test that unrecognized craft-like errors are handled specially"""


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        pytest.param(
            RuntimeError("Lifecycle run failed!"),
            "RuntimeError: Lifecycle run failed!",
            id="other",
        ),
        pytest.param(
            FakeError("Lifecycle run failed!", resolution="Try harder."),
            r"Lifecycle run failed!\n.*Recommended resolution: Try harder.",
            id="craft-like",
        ),
    ],
)
@pytest.mark.parametrize("command_cls", [*MANAGED_LIFECYCLE_COMMANDS, PackCommand])
def test_debug(
    app_metadata: AppMetadata,
    fake_services: ServiceFactory,
    mocker: pytest_mock.MockFixture,
    mock_subprocess_run: mock.MagicMock,
    error: BaseException,
    expected: str,
    command_cls: type[AppCommand],
) -> None:
    parsed_args = argparse.Namespace(destructive_mode=True, parts=None, debug=True)

    # Make lifecycle.run() raise an error.
    mocker.patch.object(fake_services.lifecycle, "run", side_effect=error)
    command = command_cls(
        {
            "app": app_metadata,
            "services": fake_services,
        }
    )

    with pytest.raises(type(error)):
        command.run(parsed_args)

    mock_subprocess_run.assert_called_once_with(["bash"], check=False)

    logs = craft_cli.emit.log_filepath.read_text()
    assert re.search(expected, logs)


def test_debug_pack(
    app_metadata,
    fake_services,
    mocker,
    mock_subprocess_run,
):
    """Same as test_debug(), but checking when the error happens when packing."""
    parsed_args = argparse.Namespace(
        destructive_mode=True, debug=True, output=pathlib.Path()
    )
    error_message = "Packing failed!"

    # Lifecycle.run() should work
    mocker.patch.object(fake_services.lifecycle, "run")
    # Package.pack() should fail
    mocker.patch.object(
        fake_services.package, "pack", side_effect=RuntimeError(error_message)
    )
    mocker.patch.object(fake_services.package, "update_project")
    command = PackCommand(
        {
            "app": app_metadata,
            "services": fake_services,
        }
    )

    with pytest.raises(RuntimeError, match=error_message):
        command.run(parsed_args)

    mock_subprocess_run.assert_called_once_with(["bash"], check=False)


def test_run_post_prime(app_metadata, mock_services, mocker, fake_project_file):
    mock_services.get("project").configure(platform=None, build_for=None)
    command = PrimeCommand(
        {
            "app": app_metadata,
            "services": mock_services,
        }
    )
    mocked_run_post_prime_steps = mocker.patch.object(command, "_run_post_prime_steps")

    parsed_args = argparse.Namespace(
        destructive_mode=False,
        parts=[],
    )

    command.run(parsed_args)

    mocked_run_post_prime_steps.assert_not_called()


def test_run_post_prime_destructive_mode(
    app_metadata, mock_services, mocker, fake_project_file
):
    mock_services.get("project").configure(platform=None, build_for=None)
    command = PrimeCommand(
        {
            "app": app_metadata,
            "services": mock_services,
        }
    )
    mocked_run_post_prime_steps = mocker.patch.object(command, "_run_post_prime_steps")

    parsed_args = argparse.Namespace(
        destructive_mode=True,
        parts=[],
    )

    command.run(parsed_args)

    mocked_run_post_prime_steps.assert_called_once()


@pytest.mark.usefixtures("managed_mode")
def test_run_post_prime_managed_mode(
    app_metadata, mock_services, mocker, fake_project_file
):
    mock_services.get("project").configure(platform=None, build_for=None)
    command = PrimeCommand(
        {
            "app": app_metadata,
            "services": mock_services,
        }
    )
    mocked_run_post_prime_steps = mocker.patch.object(command, "_run_post_prime_steps")

    parsed_args = argparse.Namespace(
        destructive_mode=False,
        parts=[],
    )

    command.run(parsed_args)

    mocked_run_post_prime_steps.assert_called_once()


@pytest.mark.parametrize(
    ("root", "paths", "result"),
    [
        ("/", ["/foo"], ["foo"]),
        ("/foo", ["/foo/bar", "/foo/baz"], ["bar", "baz"]),
    ],
)
def test_relativize_paths_valid(root, paths, result):
    normalized_path = PackCommand._relativize_paths(
        [pathlib.Path(p) for p in paths], root=pathlib.Path(root)
    )
    assert normalized_path == [pathlib.Path(p) for p in result]


def test_relativize_paths_valid_relative(new_dir):
    normalized_path = PackCommand._relativize_paths(
        [pathlib.Path("relative")], root=new_dir
    )
    assert normalized_path == [pathlib.Path("relative")]


@pytest.mark.parametrize(
    ("root", "paths"),
    [
        ("/foo", ["relative"]),
        ("/foo", ["/not/inside/foo"]),
        ("/foo", ["/foo/bar", "/not/inside/foo"]),
    ],
)
def test_relativize_paths_invalid(root, paths):
    with pytest.raises(errors.ArtifactCreationError) as raised:
        PackCommand._relativize_paths(
            [pathlib.Path(p) for p in paths], root=pathlib.Path(root)
        )
    assert str(raised.value) == "Cannot create packages outside of the project tree."


@pytest.mark.parametrize(
    ("debug", "shell", "shell_after", "tests"),
    [
        (False, False, False, None),
        (True, True, True, "something"),
    ],
)
@pytest.mark.parametrize("fetch_service_policy", [None, "strict", "permissive"])
def test_test_run(
    mocker,
    emitter,
    mock_services,
    app_metadata,
    debug,
    shell,
    shell_after,
    tests,
    fake_project_file,
    fake_platform,
    fetch_service_policy,
):
    mock_services.get("build_plan").set_platforms(fake_platform)
    try:
        mock_services.get("build_plan").plan()
    except errors.EmptyBuildPlanError:
        pytest.skip(f"Can't build for {fake_platform}")
    mock_services.package.pack.return_value = [pathlib.Path("package.zip")]
    parsed_args = argparse.Namespace(
        parts=["my-part"],
        debug=debug,
        shell=shell,
        shell_after=shell_after,
        test_expressions=tests,
        platform=fake_platform,
        build_for=None,
        fetch_service_policy=fetch_service_policy,
    )
    command = TestCommand(
        {
            "app": app_metadata,
            "services": mock_services,
        }
    )

    command.run(parsed_args)

    mock_services.get("provider").run_managed.assert_called_once_with(
        mock_services.get("build_plan").plan()[0],
        enable_fetch_service=bool(fetch_service_policy),
    )
    mock_services.get("testing").test.assert_called_once_with(
        pathlib.Path.cwd(),
        pack_state=mock.ANY,
        shell=shell,
        shell_after=shell_after,
        debug=debug,
        test_expressions=tests,
    )


def test_get_packed_file_list_timestamp(mocker, new_dir, app_metadata, fake_services):
    command = PackCommand({"app": app_metadata, "services": fake_services})
    mocker.patch.object(command._services.lifecycle.project_info, "work_dir", new_dir)

    path = pathlib.Path(".craft/packed-files")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()
    expected_time = path.stat().st_mtime_ns
    actual_time = command._get_packed_file_list_timestamp()

    assert actual_time == expected_time


def test_get_packed_file_list_timestamp_no_file(
    mocker, new_dir, app_metadata, fake_services
):
    command = PackCommand({"app": app_metadata, "services": fake_services})
    mocker.patch.object(command._services.lifecycle.project_info, "work_dir", new_dir)
    assert command._get_packed_file_list_timestamp() is None


@pytest.mark.parametrize(
    ("artifact", "resources"),
    [
        (None, None),
        (pathlib.Path("foo"), None),
        (pathlib.Path("foo"), {"bar": pathlib.Path("bar.tar.gz")}),
    ],
)
def test_save_packed_file_list(
    mocker, tmp_path, app_metadata, fake_services, artifact, resources
):
    command = PackCommand({"app": app_metadata, "services": fake_services})
    mocker.patch.object(command._services.lifecycle.project_info, "work_dir", tmp_path)

    command._save_packed_file_list(artifact, resources)

    data = models.PackState.from_yaml_file(tmp_path / ".craft" / "packed-files")
    assert data.artifact == artifact
    assert data.resources == resources


@pytest.mark.parametrize(
    ("artifact", "resources"),
    [
        (None, None),
        (pathlib.Path("foo"), None),
        (pathlib.Path("foo"), {"bar": pathlib.Path("bar.gz")}),
    ],
)
def test_load_packed_file_list(
    mocker, tmp_path, app_metadata, fake_services, artifact, resources
):
    command = PackCommand({"app": app_metadata, "services": fake_services})
    mocker.patch.object(command._services.lifecycle.project_info, "work_dir", tmp_path)

    data = models.PackState(artifact=artifact, resources=resources)
    (tmp_path / ".craft").mkdir()
    data.to_yaml_file(tmp_path / ".craft" / "packed-files")

    artifact, resources = command._load_packed_file_list()

    assert artifact == data.artifact
    assert resources == data.resources


def test_load_packed_file_list_no_file(mocker, tmp_path, app_metadata, fake_services):
    command = PackCommand({"app": app_metadata, "services": fake_services})
    mocker.patch.object(command._services.lifecycle.project_info, "work_dir", tmp_path)

    artifact, resources = command._load_packed_file_list()

    assert artifact is None
    assert resources is None


@pytest.mark.parametrize(
    ("artifact", "resources", "files", "result"),
    [
        (None, None, [], False),
        (pathlib.Path("foo"), None, [], True),
        (pathlib.Path("foo"), None, [pathlib.Path("foo")], False),
        (
            pathlib.Path("foo"),
            {"bar": pathlib.Path("bar.gz")},
            [pathlib.Path("foo")],
            True,
        ),
        (
            pathlib.Path("foo"),
            {"bar": pathlib.Path("bar.gz")},
            [pathlib.Path("foo"), pathlib.Path("bar.gz")],
            False,
        ),
    ],
)
def test_is_missing_packed_files(
    new_dir, app_metadata, fake_services, artifact, resources, files, result
):
    command = PackCommand({"app": app_metadata, "services": fake_services})

    for f in files:
        f.touch()

    assert command._is_missing_packed_files(artifact, resources) == result


@pytest.mark.parametrize(
    ("pack_time", "prime_time", "is_missing", "result"),
    [
        (None, None, False, False),  # No times available
        (None, 1000, False, False),  # Primed but pack time not available
        (1500, 1000, False, True),  # Pack is more recent and files exist
        (1500, 1000, True, False),  # No packed artifacts
        (1500, None, False, False),  # No prime time (should never happen)
        (1000, 1500, False, False),  # Prime time is more recent than pack
    ],
)
def test_is_already_packed(
    mocker, app_metadata, fake_services, pack_time, prime_time, is_missing, result
):
    command = PackCommand({"app": app_metadata, "services": fake_services})
    mocker.patch(
        "craft_application.commands.lifecycle.PackCommand._get_packed_file_list_timestamp",
        return_value=pack_time,
    )
    mocker.patch.object(LifecycleService, "prime_state_timestamp", prime_time)
    mocker.patch(
        "craft_application.commands.lifecycle.PackCommand._is_missing_packed_files",
        return_value=is_missing,
    )

    assert command._is_already_packed() == result
