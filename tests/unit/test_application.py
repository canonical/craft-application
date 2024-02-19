# This file is part of craft_application.
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
"""Unit tests for craft-application app classes."""
import argparse
import dataclasses
import importlib
import importlib.metadata
import logging
import pathlib
import re
import subprocess
import sys
from textwrap import dedent
from typing import Any
from unittest import mock

import craft_application
import craft_application.errors
import craft_cli
import craft_parts
import craft_providers
import pytest
import pytest_check
from craft_application import application, commands, errors, secrets, services, util
from craft_application.models import BuildInfo
from craft_application.util import (
    get_host_architecture,  # pyright: ignore[reportGeneralTypeIssues]
)
from craft_parts.plugins.plugins import PluginType
from craft_providers import bases
from overrides import override

EMPTY_COMMAND_GROUP = craft_cli.CommandGroup("FakeCommands", [])
BASIC_PROJECT_YAML = """
name: myproject
version: 1.0
parts:
  mypart:
    plugin: nil
"""


@pytest.mark.parametrize("summary", ["A summary", None])
def test_app_metadata_post_init_correct(summary):
    app = application.AppMetadata("craft-application", summary)

    pytest_check.equal(app.version, craft_application.__version__)
    pytest_check.is_not_none(app.summary)


def test_app_metadata_version_attribute(tmp_path, monkeypatch):
    """Set the AppMetadata version from the main app package."""
    monkeypatch.syspath_prepend(tmp_path)
    (tmp_path / "dummycraft_version.py").write_text("__version__ = '1.2.3'")

    app = application.AppMetadata(name="dummycraft_version", summary="dummy craft")
    assert app.version == "1.2.3"


def test_app_metadata_importlib(tmp_path, monkeypatch, mocker):
    """Set the AppMetadata version via importlib."""
    monkeypatch.syspath_prepend(tmp_path)
    (tmp_path / "dummycraft_importlib.py").write_text("print('hi')")

    mocker.patch.object(importlib.metadata, "version", return_value="4.5.6")

    app = application.AppMetadata(name="dummycraft_importlib", summary="dummy craft")
    assert app.version == "4.5.6"


def test_app_metadata_dev():
    app = application.AppMetadata(name="dummycraft_dev", summary="dummy craft")
    assert app.version == "dev"


def test_app_metadata_default_project_variables():
    app = application.AppMetadata(name="dummycraft_dev", summary="dummy craft")
    assert app.project_variables == ["version"]


def test_app_metadata_default_mandatory_adoptable_fields():
    app = application.AppMetadata(name="dummycraft_dev", summary="dummy craft")
    assert app.mandatory_adoptable_fields == ["version"]


class FakeApplication(application.Application):
    """An application class explicitly for testing. Adds some convenient test hooks."""

    platform: str = "unknown-platform"
    build_on: str = "unknown-build-on"
    build_for: str | None = "unknown-build-for"

    def set_project(self, project):
        self._Application__project = project

    @override
    def _extra_yaml_transform(
        self,
        yaml_data: dict[str, Any],
        *,
        build_on: str,
        build_for: str | None,
    ) -> dict[str, Any]:
        self.build_on = build_on
        self.build_for = build_for

        return yaml_data


@pytest.fixture()
def app(app_metadata, fake_services):
    return FakeApplication(app_metadata, fake_services)


class FakePlugin(craft_parts.plugins.Plugin):
    def __init__(self, properties, part_info):
        pass

    def get_build_commands(self) -> list[str]:
        return []

    def get_build_snaps(self) -> set[str]:
        return set()

    def get_build_packages(self) -> set[str]:
        return set()

    def get_build_environment(self) -> dict[str, str]:
        return {}

    def get_build_sources(self) -> set[str]:
        return set()


@pytest.fixture()
def fake_plugin(app_metadata, fake_services):
    return FakePlugin(app_metadata, fake_services)


@pytest.fixture()
def mock_dispatcher(monkeypatch):
    dispatcher = mock.Mock(spec_set=craft_cli.Dispatcher)
    monkeypatch.setattr("craft_cli.Dispatcher", mock.Mock(return_value=dispatcher))
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


def _create_command(command_name):
    class _FakeCommand(commands.AppCommand):
        name = command_name

    return _FakeCommand


def test_merge_command_groups(app):
    app.add_command_group(
        "Lifecycle", [_create_command("wash"), _create_command("fold")]
    )
    app.add_command_group("Other", [_create_command("list")])
    app.add_command_group("Specific", [_create_command("reticulate")])

    lifecycle = commands.get_lifecycle_command_group()
    other = commands.get_other_command_group()

    command_groups = app.command_groups
    group_name_to_command_name = {
        group.name: [c.name for c in group.commands] for group in command_groups
    }

    assert group_name_to_command_name == {
        "Lifecycle": [c.name for c in lifecycle.commands] + ["wash", "fold"],
        "Other": [c.name for c in other.commands] + ["list"],
        "Specific": ["reticulate"],
    }


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


def test_run_managed_success(app, fake_project, fake_build_plan):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services.provider = mock_provider
    app.project = fake_project
    app._build_plan = fake_build_plan
    arch = get_host_architecture()

    app.run_managed(None, arch)

    assert (
        mock.call(
            fake_build_plan[0],
            work_dir=mock.ANY,
        )
        in mock_provider.instance.mock_calls
    )


def test_run_managed_failure(app, fake_project, fake_build_plan):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    instance = mock_provider.instance.return_value.__enter__.return_value
    instance.execute_run.side_effect = subprocess.CalledProcessError(1, [])
    app.services.provider = mock_provider
    app.project = fake_project
    app._build_plan = fake_build_plan

    with pytest.raises(craft_providers.ProviderError) as exc_info:
        app.run_managed(None, get_host_architecture())

    assert exc_info.value.brief == "Failed to execute testcraft in instance."


@pytest.mark.enable_features("build_secrets")
def test_run_managed_secrets(app, fake_project, fake_build_plan):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    instance = mock_provider.instance.return_value.__enter__.return_value
    mock_execute = instance.execute_run
    app.services.provider = mock_provider
    app.project = fake_project
    app._build_plan = fake_build_plan

    fake_encoded_environment = {
        "CRAFT_TEST": "banana",
    }
    app._secrets = secrets.BuildSecrets(
        environment=fake_encoded_environment,
        secret_strings=set(),
    )

    app.run_managed(None, get_host_architecture())

    # Check that the encoded secrets were propagated to the managed instance.
    assert len(mock_execute.mock_calls) == 1
    call = mock_execute.mock_calls[0]
    execute_env = call.kwargs["env"]
    assert execute_env["CRAFT_TEST"] == "banana"


def test_run_managed_multiple(app, fake_project):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services.provider = mock_provider
    app.set_project(fake_project)

    arch = get_host_architecture()
    info1 = BuildInfo("a1", arch, "arch1", bases.BaseName("base", "1"))
    info2 = BuildInfo("a2", arch, "arch2", bases.BaseName("base", "2"))
    app._build_plan = [info1, info2]

    app.run_managed(None, None)

    assert mock.call(info2, work_dir=mock.ANY) in mock_provider.instance.mock_calls
    assert mock.call(info1, work_dir=mock.ANY) in mock_provider.instance.mock_calls


def test_run_managed_specified_arch(app, fake_project):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services.provider = mock_provider
    app.set_project(fake_project)

    arch = get_host_architecture()
    info1 = BuildInfo("a1", arch, "arch1", bases.BaseName("base", "1"))
    info2 = BuildInfo("a2", arch, "arch2", bases.BaseName("base", "2"))
    app._build_plan = [info1, info2]

    app.run_managed(None, "arch2")

    assert mock.call(info2, work_dir=mock.ANY) in mock_provider.instance.mock_calls
    assert mock.call(info1, work_dir=mock.ANY) not in mock_provider.instance.mock_calls


def test_run_managed_specified_platform(app, fake_project):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services.provider = mock_provider
    app.set_project(fake_project)

    arch = get_host_architecture()
    info1 = BuildInfo("a1", arch, "arch1", bases.BaseName("base", "1"))
    info2 = BuildInfo("a2", arch, "arch2", bases.BaseName("base", "2"))
    app._build_plan = [info1, info2]

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


def test_craft_lib_log_level(app_metadata, fake_services):
    craft_libs = [
        "craft_archives",
        "craft_parts",
        "craft_providers",
        "craft_store",
        "craft_application.remote",
    ]

    # The logging module is stateful and global, so first lets clear the logging level
    # that another test might have already set.
    for craft_lib in craft_libs:
        logger = logging.getLogger(craft_lib)
        logger.setLevel(logging.NOTSET)

    app = FakeApplication(app_metadata, fake_services)
    with pytest.raises(SystemExit):
        app.run()

    for craft_lib in craft_libs:
        logger = logging.getLogger(craft_lib)
        assert logger.level == logging.DEBUG


def test_gets_project(monkeypatch, tmp_path, app_metadata, fake_services):
    project_file = tmp_path / "testcraft.yaml"
    project_file.write_text(BASIC_PROJECT_YAML)
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull", "--destructive-mode"])

    app = FakeApplication(app_metadata, fake_services)
    app.project_dir = tmp_path

    fake_services.project = None

    app.run()

    assert fake_services.project is not None
    assert app.project is not None


def test_fails_without_project(
    monkeypatch, capsys, tmp_path, app_metadata, fake_services
):
    monkeypatch.setattr(sys, "argv", ["testcraft", "prime"])

    app = FakeApplication(app_metadata, fake_services)
    app.project_dir = tmp_path

    fake_services.project = None

    assert app.run() == 70  # noqa: PLR2004

    assert "No such file or directory" in capsys.readouterr().err


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


def test_show_app_name_and_version(monkeypatch, capsys, app):
    """Test that the app name and version are shown during logging."""
    monkeypatch.setattr(sys, "argv", ["testcraft", "--verbosity=trace"])

    with pytest.raises(SystemExit):
        app.run()

    _, err = capsys.readouterr()
    assert f"Starting testcraft, version {app.app.version}" in err


def test_pre_run_project_dir_managed(app):
    app.is_managed = lambda: True
    dispatcher = mock.Mock(spec_set=craft_cli.Dispatcher)

    app._pre_run(dispatcher)

    assert app.project_dir == pathlib.Path("/root/project")


@pytest.mark.parametrize("project_dir", ["/", ".", "relative/dir", "/absolute/dir"])
def test_pre_run_project_dir_success_unmanaged(app, fs, project_dir):
    fs.create_dir(project_dir)
    app.is_managed = lambda: False
    dispatcher = mock.Mock(spec_set=craft_cli.Dispatcher)
    dispatcher.parsed_args.return_value.project_dir = project_dir

    app._pre_run(dispatcher)

    assert app.project_dir == pathlib.Path(project_dir).expanduser().resolve()


@pytest.mark.parametrize("project_dir", ["relative/file", "/absolute/file"])
def test_pre_run_project_dir_not_a_directory(app, fs, project_dir):
    fs.create_file(project_dir)
    dispatcher = mock.Mock(spec_set=craft_cli.Dispatcher)
    dispatcher.parsed_args.return_value.project_dir = project_dir

    with pytest.raises(errors.ProjectFileMissingError, match="not a directory"):
        app._pre_run(dispatcher)


@pytest.mark.parametrize("load_project", [True, False])
@pytest.mark.parametrize("return_code", [None, 0, 1])
def test_run_success_unmanaged(
    monkeypatch, emitter, check, app, fake_project, return_code, load_project
):
    class UnmanagedCommand(commands.AppCommand):
        name = "pass"
        help_msg = "Return without doing anything"
        overview = "Return without doing anything"
        always_load_project = load_project

        def run(self, parsed_args: argparse.Namespace):  # noqa: ARG002
            return return_code

    monkeypatch.setattr(sys, "argv", ["testcraft", "pass"])

    app.add_command_group("test", [UnmanagedCommand])
    app.set_project(fake_project)

    check.equal(app.run(), return_code or 0)
    with check:
        emitter.assert_debug("Preparing application...")
    with check:
        emitter.assert_debug("Running testcraft pass on host")


def test_run_success_managed(monkeypatch, app, fake_project, mocker):
    mocker.patch.object(app, "get_project", return_value=fake_project)
    app.run_managed = mock.Mock()
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull"])

    pytest_check.equal(app.run(), 0)

    app.run_managed.assert_called_once_with(None, None)  # --build-for not used


def test_run_success_managed_with_arch(monkeypatch, app, fake_project, mocker):
    mocker.patch.object(app, "get_project", return_value=fake_project)
    app.run_managed = mock.Mock()
    arch = get_host_architecture()
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull", f"--build-for={arch}"])

    pytest_check.equal(app.run(), 0)

    app.run_managed.assert_called_once()


def test_run_success_managed_with_platform(monkeypatch, app, fake_project, mocker):
    mocker.patch.object(app, "get_project", return_value=fake_project)
    app.run_managed = mock.Mock()
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull", "--platform=foo"])

    pytest_check.equal(app.run(), 0)

    app.run_managed.assert_called_once_with("foo", None)


@pytest.mark.parametrize("return_code", [None, 0, 1])
def test_run_success_managed_inside_managed(
    monkeypatch, check, app, fake_project, mock_dispatcher, return_code, mocker
):
    mocker.patch.object(app, "get_project", return_value=fake_project)
    mocker.patch.object(
        mock_dispatcher, "parsed_args", return_value={"platform": "foo"}
    )
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
        (
            craft_cli.ArgumentParsingError("Argument parsing error"),
            64,
            "Argument parsing error\n",
        ),
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
    app.set_project(fake_project)
    mock_dispatcher.load_command.side_effect = error
    mock_dispatcher.pre_parse_args.return_value = {}
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull"])

    pytest_check.equal(app.run(), return_code)
    out, err = capsys.readouterr()
    assert err.startswith(error_msg)


@pytest.mark.parametrize("error", [KeyError(), ValueError(), Exception()])
def test_run_error_debug(monkeypatch, mock_dispatcher, app, fake_project, error):
    app.set_project(fake_project)
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
    project_path.write_text(BASIC_PROJECT_YAML)
    monkeypatch.chdir(project_dir)

    return project_path


@pytest.mark.usefixtures("fake_project_file")
def test_work_dir_project_non_managed(monkeypatch, app_metadata, fake_services):
    monkeypatch.setenv(fake_services.ProviderClass.managed_mode_env_var, "0")

    app = application.Application(app_metadata, fake_services)
    assert app._work_dir == pathlib.Path.cwd()

    project = app.get_project(build_for=get_host_architecture())

    # Make sure the project is loaded correctly (from the cwd)
    assert project is not None
    assert project.name == "myproject"
    assert project.version == "1.0"


@pytest.mark.usefixtures("fake_project_file")
def test_work_dir_project_managed(monkeypatch, app_metadata, fake_services):
    monkeypatch.setenv(fake_services.ProviderClass.managed_mode_env_var, "1")

    app = application.Application(app_metadata, fake_services)
    assert app._work_dir == pathlib.PosixPath("/root")

    project = app.get_project(build_for=get_host_architecture())

    # Make sure the project is loaded correctly (from the cwd)
    assert project is not None

    assert project.name == "myproject"
    assert project.version == "1.0"


@pytest.fixture()
def environment_project(monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_path = project_dir / "testcraft.yaml"
    project_path.write_text(
        dedent(
            """
        name: myproject
        version: 1.2.3
        parts:
          mypart:
            plugin: nil
            source-tag: v$CRAFT_PROJECT_VERSION
        """
        )
    )
    monkeypatch.chdir(project_dir)

    return project_path


@pytest.mark.usefixtures("environment_project")
def test_applcation_expand_environment(app_metadata, fake_services):
    app = application.Application(app_metadata, fake_services)
    project = app.get_project(build_for=get_host_architecture())

    # Make sure the project is loaded correctly (from the cwd)
    assert project is not None
    assert project.parts["mypart"]["source-tag"] == "v1.2.3"


@pytest.fixture()
def build_secrets_project(monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_path = project_dir / "testcraft.yaml"
    project_path.write_text(
        dedent(
            """
        name: myproject
        version: 1.2.3
        parts:
          mypart:
            plugin: nil
            source: $(HOST_SECRET:echo ${SECRET_VAR_1})/project
            build-environment:
              - MY_VAR: $(HOST_SECRET:echo ${SECRET_VAR_2})
        """
        )
    )
    monkeypatch.chdir(project_dir)

    return project_path


@pytest.mark.usefixtures("build_secrets_project")
@pytest.mark.enable_features("build_secrets")
def test_application_build_secrets(app_metadata, fake_services, monkeypatch, mocker):
    monkeypatch.setenv("SECRET_VAR_1", "source-folder")
    monkeypatch.setenv("SECRET_VAR_2", "secret-value")
    spied_set_secrets = mocker.spy(craft_cli.emit, "set_secrets")

    app = application.Application(app_metadata, fake_services)
    project = app.get_project(build_for=get_host_architecture())

    # Make sure the project is loaded correctly (from the cwd)
    assert project is not None

    mypart = project.parts["mypart"]
    assert mypart["source"] == "source-folder/project"
    assert mypart["build-environment"][0]["MY_VAR"] == "secret-value"

    spied_set_secrets.assert_called_once_with(list({"source-folder", "secret-value"}))


@pytest.mark.usefixtures("fake_project_file")
def test_get_project_current_dir(app):
    # Load a project file from the current directory
    project = app.get_project()

    # Check that it caches that project.
    assert app.get_project() is project, "Project file was not cached."


@pytest.mark.usefixtures("fake_project_file")
def test_get_project_all_platform(app):
    app.get_project(platform="foo")


@pytest.mark.usefixtures("fake_project_file")
def test_get_project_invalid_platform(app):
    # Load a project file from the current directory

    with pytest.raises(errors.InvalidPlatformError) as raised:
        app.get_project(platform="invalid")

    assert (
        str(raised.value) == "Platform 'invalid' not found in the project definition."
    )


@pytest.mark.usefixtures("fake_project_file")
def test_get_project_property(app):
    assert app.project == app.get_project()


def test_get_cache_dir(tmp_path, app):
    """Test that the cache dir is created and returned."""
    with mock.patch.dict("os.environ", {"XDG_CACHE_HOME": str(tmp_path / "cache")}):
        assert app.cache_dir == tmp_path / "cache" / "testcraft"
        assert app.cache_dir.is_dir()


def test_get_cache_dir_exists(tmp_path, app):
    """Test that the cache dir is returned when already exists."""
    (tmp_path / "cache" / "testcraft").mkdir(parents=True, exist_ok=True)
    with mock.patch.dict("os.environ", {"XDG_CACHE_HOME": str(tmp_path / "cache")}):
        assert app.cache_dir == tmp_path / "cache" / "testcraft"
        assert app.cache_dir.is_dir()


def test_get_cache_dir_is_file(tmp_path, app):
    """Test that the cache dir path is not valid when it is a file."""
    (tmp_path / "cache").mkdir(parents=True, exist_ok=True)
    (tmp_path / "cache" / "testcraft").write_text("test")
    with mock.patch.dict("os.environ", {"XDG_CACHE_HOME": str(tmp_path / "cache")}):
        with pytest.raises(application.PathInvalidError, match="is not a directory"):
            assert app.cache_dir == tmp_path / "cache" / "testcraft"


def test_get_cache_dir_parent_read_only(tmp_path, app):
    """Test that the cache dir path is not valid when its parent is read-only."""
    (tmp_path / "cache").mkdir(parents=True, exist_ok=True)
    (tmp_path / "cache").chmod(0o400)
    with mock.patch.dict("os.environ", {"XDG_CACHE_HOME": str(tmp_path / "cache")}):
        with pytest.raises(
            application.PathInvalidError,
            match="Unable to create/access cache directory: Permission denied",
        ):
            assert app.cache_dir == tmp_path / "cache" / "testcraft"


def test_register_plugins(mocker, app_metadata, fake_services):
    """Test that the App registers plugins when initialing."""
    reg = mocker.patch("craft_parts.plugins.register")

    class FakeApplicationWithPlugins(FakeApplication):
        def _get_app_plugins(self) -> dict[str, PluginType]:
            return {"fake": FakePlugin}

    app = FakeApplicationWithPlugins(app_metadata, fake_services)

    with pytest.raises(SystemExit):
        app.run()

    assert reg.call_count == 1
    assert reg.call_args[0][0] == {"fake": FakePlugin}


def test_register_plugins_default(mocker, app_metadata, fake_services):
    """Test that the App registers default plugins when initialing."""
    reg = mocker.patch("craft_parts.plugins.register")

    app = FakeApplication(app_metadata, fake_services)
    with pytest.raises(SystemExit):
        app.run()

    assert reg.call_count == 0


def test_extra_yaml_transform(tmp_path, app_metadata, fake_services):
    project_file = tmp_path / "testcraft.yaml"
    project_file.write_text(BASIC_PROJECT_YAML)

    app = FakeApplication(app_metadata, fake_services)
    app.project_dir = tmp_path
    _ = app.get_project(build_for="fake-build-for")

    assert app.build_on == util.get_host_architecture()
    assert app.build_for == "fake-build-for"


def test_mandatory_adoptable_fields(tmp_path, app_metadata, fake_services):
    """Verify if mandatory adoptable fields are defined if not using adopt-info."""
    project_file = tmp_path / "testcraft.yaml"
    project_file.write_text(BASIC_PROJECT_YAML)
    app_metadata = dataclasses.replace(
        app_metadata, mandatory_adoptable_fields=["license"]
    )

    app = application.Application(app_metadata, fake_services)
    app.project_dir = tmp_path

    with pytest.raises(errors.CraftValidationError) as exc_info:
        _ = app.get_project(build_for=get_host_architecture())

    assert (
        str(exc_info.value)
        == "Required field 'license' is not set and 'adopt-info' not used."
    )
