# This file is part of craft_application.
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
"""Unit tests for craft-application app classes."""
import argparse
import pathlib
import re
import subprocess
import sys
from textwrap import dedent
from unittest import mock

import craft_application
import craft_cli
import craft_parts
import craft_providers
import pytest
import pytest_check
from craft_application import application, commands, services
from craft_application.models import BuildInfo
from craft_application.util import (
    get_host_architecture,  # pyright: ignore[reportGeneralTypeIssues]
)
from craft_providers import bases

EMPTY_COMMAND_GROUP = craft_cli.CommandGroup("FakeCommands", [])


@pytest.mark.parametrize("summary", ["A summary", None])
def test_app_metadata_post_init_correct(summary):
    app = application.AppMetadata("craft-application", summary)

    pytest_check.equal(app.version, craft_application.__version__)
    pytest_check.is_not_none(app.summary)


@pytest.fixture()
def app(app_metadata, fake_services):
    return application.Application(app_metadata, fake_services)


@pytest.fixture()
def mock_dispatcher(monkeypatch):
    dispatcher = mock.Mock(spec_set=application._Dispatcher)
    monkeypatch.setattr(
        "craft_application.application._Dispatcher", mock.Mock(return_value=dispatcher)
    )
    return dispatcher


@pytest.mark.parametrize(
    ("added_groups", "expected"),
    [
        (
            [],
            [
                commands.get_lifecycle_command_group(),
                commands.get_other_command_group(),
            ],
        ),
        (
            [[]],
            [
                commands.get_lifecycle_command_group(),
                commands.get_other_command_group(),
                EMPTY_COMMAND_GROUP,
            ],
        ),
    ],
)
def test_add_get_command_groups(app, added_groups, expected):
    for group in added_groups:
        app.add_command_group("FakeCommands", group)

    assert app.command_groups == expected


@pytest.mark.parametrize(
    ("provider_managed", "expected"),
    [(True, pathlib.PurePosixPath("/tmp/testcraft.log")), (False, None)],
)
def test_log_path(monkeypatch, app, provider_managed, expected):
    monkeypatch.setattr(
        app.services.ProviderClass, "is_managed", lambda: provider_managed
    )

    actual = app.log_path

    assert actual == expected


def test_run_managed_success(app, fake_project):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services.provider = mock_provider
    app.project = fake_project

    arch = get_host_architecture()
    app.run_managed(None, arch)

    assert (
        mock.call(
            BuildInfo("foo", "amd64", "amd64", bases.BaseName("ubuntu", "22.04")),
            work_dir=mock.ANY,
        )
        in mock_provider.instance.mock_calls
    )


def test_run_managed_failure(app, fake_project):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    instance = mock_provider.instance.return_value.__enter__.return_value
    instance.execute_run.side_effect = subprocess.CalledProcessError(1, [])
    app.services.provider = mock_provider
    app.project = fake_project

    with pytest.raises(craft_providers.ProviderError) as exc_info:
        app.run_managed(None, get_host_architecture())

    assert exc_info.value.brief == "Failed to execute testcraft in instance."


def test_run_managed_multiple(app, fake_project, monkeypatch):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services.provider = mock_provider
    app.project = fake_project

    arch = get_host_architecture()
    info1 = BuildInfo("a1", arch, "arch1", bases.BaseName("base", "1"))
    info2 = BuildInfo("a2", arch, "arch2", bases.BaseName("base", "2"))

    monkeypatch.setattr(
        app.project.__class__,
        "get_build_plan",
        lambda _: [info1, info2],
    )
    app.run_managed(None, None)

    assert mock.call(info2, work_dir=mock.ANY) in mock_provider.instance.mock_calls
    assert mock.call(info1, work_dir=mock.ANY) in mock_provider.instance.mock_calls


def test_run_managed_specified_arch(app, fake_project, monkeypatch):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services.provider = mock_provider
    app.project = fake_project

    arch = get_host_architecture()
    info1 = BuildInfo("a1", arch, "arch1", bases.BaseName("base", "1"))
    info2 = BuildInfo("a2", arch, "arch2", bases.BaseName("base", "2"))

    monkeypatch.setattr(
        app.project.__class__,
        "get_build_plan",
        lambda _: [info1, info2],
    )
    app.run_managed(None, "arch2")

    assert mock.call(info2, work_dir=mock.ANY) in mock_provider.instance.mock_calls
    assert mock.call(info1, work_dir=mock.ANY) not in mock_provider.instance.mock_calls


def test_run_managed_specified_platform(app, fake_project, monkeypatch):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services.provider = mock_provider
    app.project = fake_project

    arch = get_host_architecture()
    info1 = BuildInfo("a1", arch, "arch1", bases.BaseName("base", "1"))
    info2 = BuildInfo("a2", arch, "arch2", bases.BaseName("base", "2"))

    monkeypatch.setattr(
        app.project.__class__,
        "get_build_plan",
        lambda _: [info1, info2],
    )
    app.run_managed("a2", None)

    assert mock.call(info2, work_dir=mock.ANY) in mock_provider.instance.mock_calls
    assert mock.call(info1, work_dir=mock.ANY) not in mock_provider.instance.mock_calls


@pytest.mark.parametrize(
    ("managed", "error", "exit_code", "message"),
    [
        (False, craft_cli.ProvideHelpException("Hi"), 0, "Hi\n"),
        (False, craft_cli.ArgumentParsingError(":-("), 64, r":-\(\n"),
        (False, KeyboardInterrupt(), 130, r"Interrupted.\nFull execution log: '.+'\n"),
        (
            True,
            Exception("RIP"),
            70,
            r"Internal error while loading testcraft: Exception\('RIP'\)\n",
        ),
    ],
)
def test_get_dispatcher_error(
    monkeypatch, check, capsys, app, mock_dispatcher, managed, error, exit_code, message
):
    monkeypatch.setattr(app.services.ProviderClass, "is_managed", lambda: managed)
    mock_dispatcher.pre_parse_args.side_effect = error

    with pytest.raises(SystemExit) as exc_info:
        app._get_dispatcher()

    check.equal(exc_info.value.code, exit_code)
    captured = capsys.readouterr()
    check.is_true(re.fullmatch(message, captured.err), captured.err)


@pytest.mark.parametrize(
    "argv",
    [["testcraft", "--version"], ["testcraft", "-V"], ["testcraft", "pull", "-V"]],
)
def test_run_outputs_version(monkeypatch, capsys, app, argv):
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit):
        app._get_dispatcher()

    out, _ = capsys.readouterr()
    assert out == "testcraft 3.14159\n"


@pytest.mark.parametrize("return_code", [None, 0, 1])
def test_run_success_unmanaged(
    monkeypatch, emitter, check, app, fake_project, return_code
):
    class UnmanagedCommand(commands.AppCommand):
        name = "pass"
        help_msg = "Return without doing anything"
        overview = "Return without doing anything"

        def run(self, parsed_args: argparse.Namespace):  # noqa: ARG002
            return return_code

    monkeypatch.setattr(sys, "argv", ["testcraft", "pass"])

    app.add_command_group("test", [UnmanagedCommand])
    app.project = fake_project

    check.equal(app.run(), return_code or 0)
    with check:
        emitter.assert_trace("Preparing application...")
    with check:
        emitter.assert_debug("Running testcraft pass on host")


def test_run_success_managed(monkeypatch, app, fake_project):
    app.project = fake_project
    app.run_managed = mock.Mock()
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull"])

    pytest_check.equal(app.run(), 0)

    app.run_managed.assert_called_once_with(None, None)  # --build-for not used


def test_run_success_managed_with_arch(monkeypatch, app, fake_project):
    app.project = fake_project
    app.run_managed = mock.Mock()
    arch = get_host_architecture()
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull", f"--build-for={arch}"])

    pytest_check.equal(app.run(), 0)

    app.run_managed.assert_called_once_with(None, arch)


def test_run_success_managed_with_platform(monkeypatch, app, fake_project):
    app.project = fake_project
    app.run_managed = mock.Mock()
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull", "--platform=foo"])

    pytest_check.equal(app.run(), 0)

    app.run_managed.assert_called_once_with("foo", None)


@pytest.mark.parametrize("return_code", [None, 0, 1])
def test_run_success_managed_inside_managed(
    monkeypatch, check, app, fake_project, mock_dispatcher, return_code
):
    app.project = fake_project
    app.run_managed = mock.Mock()
    mock_dispatcher.run.return_value = return_code
    mock_dispatcher.pre_parse_args.return_value = {}
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull"])
    monkeypatch.setenv("CRAFT_MANAGED_MODE", "1")

    check.equal(app.run(), return_code or 0)
    with check:
        app.run_managed.assert_not_called()
    with check:
        mock_dispatcher.run.assert_called_once_with()


@pytest.mark.parametrize(
    ("error", "return_code", "error_msg"),
    [
        (KeyboardInterrupt(), 130, "Interrupted.\n"),
        (craft_cli.CraftError("msg"), 1, "msg\n"),
        (craft_parts.PartsError("unable to pull"), 1, "unable to pull\n"),
        (craft_providers.ProviderError("fail to launch"), 1, "fail to launch\n"),
        (Exception(), 70, "testcraft internal error: Exception()\n"),
    ],
)
def test_run_error(
    monkeypatch,
    capsys,
    mock_dispatcher,
    app,
    fake_project,
    error,
    return_code,
    error_msg,
):
    app.project = fake_project
    mock_dispatcher.load_command.side_effect = error
    mock_dispatcher.pre_parse_args.return_value = {}
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull"])

    pytest_check.equal(app.run(), return_code)
    out, err = capsys.readouterr()
    assert err.startswith(error_msg)


@pytest.mark.parametrize("error", [KeyError(), ValueError(), Exception()])
def test_run_error_debug(monkeypatch, mock_dispatcher, app, fake_project, error):
    app.project = fake_project
    mock_dispatcher.load_command.side_effect = error
    mock_dispatcher.pre_parse_args.return_value = {}
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull"])
    monkeypatch.setenv("CRAFT_DEBUG", "1")

    with pytest.raises(error.__class__):
        app.run()


_base = bases.BaseName("", "")
_on_a_for_a = BuildInfo("p1", "a", "a", _base)
_on_a_for_b = BuildInfo("p2", "a", "b", _base)


@pytest.mark.parametrize(
    ("plan", "platform", "build_for", "host_arch", "result"),
    [
        ([_on_a_for_a], None, None, "a", [_on_a_for_a]),
        ([_on_a_for_a], "p1", None, "a", [_on_a_for_a]),
        ([_on_a_for_a], "p2", None, "a", []),
        ([_on_a_for_a], None, "a", "a", [_on_a_for_a]),
        ([_on_a_for_a], "p1", "a", "a", [_on_a_for_a]),
        ([_on_a_for_a], "p2", "a", "a", []),
        ([_on_a_for_a], None, "b", "a", []),
        ([_on_a_for_a], None, "a", "b", []),
        ([_on_a_for_a, _on_a_for_b], None, "b", "a", [_on_a_for_b]),
        ([_on_a_for_a, _on_a_for_b], "p1", "b", "a", []),
        ([_on_a_for_a, _on_a_for_b], "p2", "b", "a", [_on_a_for_b]),
        ([_on_a_for_a, _on_a_for_b], None, "b", "b", []),
        ([_on_a_for_a, _on_a_for_b], None, None, "b", []),
        ([_on_a_for_a, _on_a_for_b], "p2", None, "b", []),
        ([_on_a_for_a, _on_a_for_b], None, None, "a", [_on_a_for_a, _on_a_for_b]),
        ([_on_a_for_a, _on_a_for_b], "p2", None, "a", [_on_a_for_b]),
    ],
)
def test_filter_plan(mocker, plan, platform, build_for, host_arch, result):
    mocker.patch("craft_application.util.get_host_architecture", return_value=host_arch)
    assert application._filter_plan(plan, platform, build_for) == result


@pytest.fixture()
def fake_project_file(monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_path = project_dir / "testcraft.yaml"
    project_path.write_text(
        dedent(
            """
        name: myproject
        version: 1.0
        parts:
          mypart:
            plugin: nil
        """
        )
    )
    monkeypatch.chdir(project_dir)

    return project_path


@pytest.mark.usefixtures("fake_project_file")
def test_work_dir_project_non_managed(monkeypatch, app_metadata, fake_services):
    monkeypatch.setenv(fake_services.ProviderClass.managed_mode_env_var, "0")

    app = application.Application(app_metadata, fake_services)
    assert app._work_dir == pathlib.Path.cwd()

    # Make sure the project is loaded correctly (from the cwd)
    assert app.project.name == "myproject"
    assert app.project.version == "1.0"


@pytest.mark.usefixtures("fake_project_file")
def test_work_dir_project_managed(monkeypatch, app_metadata, fake_services):
    monkeypatch.setenv(fake_services.ProviderClass.managed_mode_env_var, "1")

    app = application.Application(app_metadata, fake_services)
    assert app._work_dir == pathlib.PosixPath("/root")

    # Make sure the project is loaded correctly (from the cwd)
    assert app.project.name == "myproject"
    assert app.project.version == "1.0"
