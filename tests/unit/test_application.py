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
import importlib
import importlib.metadata
import logging
import pathlib
import re
import subprocess
import sys
from textwrap import dedent
from unittest import mock

import craft_application
import craft_application.errors
import craft_cli
import craft_cli.pytest_plugin
import craft_parts
import craft_platforms
import craft_providers
import pytest
import pytest_check
import pytest_mock
from craft_application import (
    application,
    commands,
    errors,
    services,
)
from craft_application.commands import (
    AppCommand,
    get_lifecycle_command_group,
    get_other_command_group,
)
from craft_application.util import (
    get_host_architecture,  # pyright: ignore[reportGeneralTypeIssues]
)
from craft_cli import CraftError, emit
from craft_parts.plugins.plugins import PluginType

from tests.conftest import FakeApplication

EMPTY_COMMAND_GROUP = craft_cli.CommandGroup("FakeCommands", [])


@pytest.mark.parametrize("summary", ["A summary", None])
def test_app_metadata_post_init_correct(summary):
    app = application.AppMetadata("craft-application", summary)

    pytest_check.equal(app.version, craft_application.__version__)
    pytest_check.is_not_none(app.summary)


def test_app_metadata_version_attribute(tmp_path, monkeypatch):
    """Set the AppMetadata version from the main app package."""
    monkeypatch.syspath_prepend(tmp_path)
    (tmp_path / "dummycraft_version.py").write_text("__version__ = '1.2.3'")

    app = application.AppMetadata(
        name="dummycraft_version",
        summary="dummy craft",
    )
    assert app.version == "1.2.3"


def test_app_metadata_importlib(tmp_path, monkeypatch, mocker):
    """Set the AppMetadata version via importlib."""
    monkeypatch.syspath_prepend(tmp_path)
    (tmp_path / "dummycraft_importlib.py").write_text("print('hi')")

    mocker.patch.object(importlib.metadata, "version", return_value="4.5.6")

    app = application.AppMetadata(
        name="dummycraft_importlib",
        summary="dummy craft",
    )
    assert app.version == "4.5.6"


def test_app_metadata_dev():
    app = application.AppMetadata(
        name="dummycraft_dev",
        summary="dummy craft",
    )
    assert app.version == "dev"


def test_app_metadata_default_project_variables():
    app = application.AppMetadata(
        name="dummycraft_dev",
        summary="dummy craft",
    )
    assert app.project_variables == ["version"]


def test_app_metadata_default_mandatory_adoptable_fields():
    app = application.AppMetadata(
        name="dummycraft_dev",
        summary="dummy craft",
    )
    assert app.mandatory_adoptable_fields == ["version"]


def test_app_project_vars_deprecated(app):
    expected = re.escape(
        "'Application._get_project_vars' is deprecated. "
        "Use 'ProjectService.project_vars' instead."
    )
    with pytest.warns(DeprecationWarning, match=expected):
        project_vars = app._get_project_vars({"version": "test-version"})

    assert project_vars == {"version": "test-version"}


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


@pytest.fixture
def fake_plugin(app_metadata, fake_services):
    return FakePlugin(app_metadata, fake_services)


@pytest.fixture
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
                EMPTY_COMMAND_GROUP,
                commands.get_lifecycle_command_group(),
                commands.get_other_command_group(),
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


def test_merge_default_commands(app):
    """Merge commands with the same name within the same groups."""
    stage_command = _create_command("stage")
    extra_lifecycle_command = _create_command("extra")
    init_command = _create_command("init")
    extra_other_command = _create_command("extra")

    app.add_command_group("Lifecycle", [stage_command, extra_lifecycle_command])
    app.add_command_group("Other", [init_command, extra_other_command])
    command_groups = app.command_groups

    # check against hardcoded list because the order is important
    assert command_groups == [
        craft_cli.CommandGroup(
            name="Lifecycle",
            commands=[
                commands.lifecycle.CleanCommand,
                commands.lifecycle.PullCommand,
                commands.lifecycle.BuildCommand,
                stage_command,
                commands.lifecycle.PrimeCommand,
                commands.lifecycle.PackCommand,
                extra_lifecycle_command,
            ],
            ordered=True,
        ),
        craft_cli.CommandGroup(
            name="Other",
            commands=[
                init_command,
                commands.other.VersionCommand,
                extra_other_command,
            ],
            ordered=False,
        ),
    ]


def test_merge_default_commands_only(app):
    """Use default commands if no app commands are provided."""
    command_groups = app.command_groups

    assert command_groups == [get_lifecycle_command_group(), get_other_command_group()]


@pytest.mark.parametrize(
    ("provider_managed", "expected"),
    [(True, pathlib.PurePosixPath("/tmp/testcraft.log")), (False, None)],
)
def test_log_path(monkeypatch, app, provider_managed, expected):
    monkeypatch.setattr(
        app.services.get_class("provider"), "is_managed", lambda: provider_managed
    )

    actual = app.log_path

    assert actual == expected


@pytest.mark.usefixtures("platform_independent_project")
def test_run_managed_success(mocker, app, fake_host_architecture):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services._services["provider"] = mock_provider
    mock_pause = mocker.spy(craft_cli.emit, "pause")

    app.run_managed("platform-independent", None)

    mock_provider.instance.assert_called_once_with(
        craft_platforms.BuildInfo(
            platform="platform-independent",
            build_on=fake_host_architecture,
            build_for="all",
            build_base=mock.ANY,
        ),
        work_dir=mock.ANY,
        clean_existing=False,
        use_base_instance=True,
    )
    mock_pause.assert_called_once_with()


def test_run_managed_failure(app, fake_project):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    instance = mock_provider.instance.return_value.__enter__.return_value
    instance.execute_run.side_effect = subprocess.CalledProcessError(1, [])
    app.services._services["provider"] = mock_provider
    app.project = fake_project

    with pytest.raises(craft_providers.ProviderError) as exc_info:
        app.run_managed(None, get_host_architecture())

    assert exc_info.value.brief == "Failed to execute testcraft in instance."


def test_run_managed_multiple(app, fake_host_architecture):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services._services["provider"] = mock_provider

    app.run_managed(None, None)

    mock_provider.instance.assert_called_with(
        craft_platforms.BuildInfo(
            platform=mock.ANY,
            build_on=fake_host_architecture,
            build_for=mock.ANY,
            build_base=mock.ANY,
        ),
        work_dir=mock.ANY,
        clean_existing=False,
        use_base_instance=True,
    )

    assert len(mock_provider.instance.mock_calls) > 1


@pytest.mark.parametrize("build_for", craft_platforms.DebianArchitecture)
def test_run_managed_specified_arch(app, fake_host_architecture, build_for):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services._services["provider"] = mock_provider

    try:
        app.run_managed(None, build_for)
    except errors.EmptyBuildPlanError:
        pytest.skip(
            reason=f"build-for {build_for} has no build-on {fake_host_architecture}"
        )

    mock_provider.instance.assert_called_with(
        craft_platforms.BuildInfo(
            platform=mock.ANY,
            build_on=fake_host_architecture,
            build_for=build_for,
            build_base=mock.ANY,
        ),
        work_dir=mock.ANY,
        clean_existing=False,
        use_base_instance=True,
    )


def test_run_managed_specified_platform(app, fake_platform, fake_host_architecture):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services._services["provider"] = mock_provider

    try:
        app.run_managed(fake_platform, None)
    except errors.EmptyBuildPlanError:
        pytest.skip(
            reason=f"Platform {fake_platform} has no builds on {fake_host_architecture}"
        )

    mock_provider.instance.assert_called_once_with(
        craft_platforms.BuildInfo(
            platform=fake_platform,
            build_on=fake_host_architecture,
            build_for=mock.ANY,
            build_base=mock.ANY,
        ),
        work_dir=mock.ANY,
        clean_existing=False,
        use_base_instance=True,
    )


def test_run_managed_empty_plan(mocker, app):
    build_plan_service = app.services.get("build_plan")
    mocker.patch.object(build_plan_service, "plan", return_value=[])

    with pytest.raises(errors.EmptyBuildPlanError):
        app.run_managed(None, None)


@pytest.mark.parametrize(
    ("parsed_args", "environ", "item", "expected"),
    [
        (argparse.Namespace(), {}, "build_for", None),
        (argparse.Namespace(build_for=None), {}, "build_for", None),
        (
            argparse.Namespace(build_for=None),
            {"CRAFT_BUILD_FOR": "arm64"},
            "build_for",
            "arm64",
        ),
        (
            argparse.Namespace(build_for=None),
            {"TESTCRAFT_BUILD_FOR": "arm64"},
            "build_for",
            "arm64",
        ),
        (
            argparse.Namespace(build_for="riscv64"),
            {"TESTCRAFT_BUILD_FOR": "arm64"},
            "build_for",
            "riscv64",
        ),
    ],
)
def test_get_arg_or_config(monkeypatch, app, parsed_args, environ, item, expected):
    for var, content in environ.items():
        monkeypatch.setenv(var, content)

    assert app.get_arg_or_config(parsed_args, item) == expected


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
@pytest.mark.usefixtures("emitter", "production_mode")
def test_get_dispatcher_error(
    monkeypatch, check, capsys, app, mock_dispatcher, managed, error, exit_code, message
):
    monkeypatch.setattr(
        app.services.get_class("provider"), "is_managed", lambda: managed
    )
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
        "craft_application",
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


def test_gets_project(monkeypatch, fake_project_file, app_metadata, fake_services):
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull", "--destructive-mode"])

    app = FakeApplication(app_metadata, fake_services)

    app.run()

    pytest_check.is_not_none(fake_services.project)
    pytest_check.is_not_none(app.project)


def test_fails_without_project(
    monkeypatch, capsys, tmp_path, app_metadata, fake_services, app, debug_mode
):
    # Set up a real project service - the fake one for testing gets a fake project!
    del app.services._services["project"]
    app.services.register("project", services.ProjectService)

    monkeypatch.setattr(sys, "argv", ["testcraft", "prime"])

    assert app.run() == 66

    assert "Project file 'testcraft.yaml' not found in" in capsys.readouterr().err


@pytest.mark.parametrize(
    "argv",
    [["testcraft", "--version"], ["testcraft", "-V"], ["testcraft", "pull", "-V"]],
)
def test_run_outputs_version(monkeypatch, emitter, app, argv):
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit):
        app._get_dispatcher()

    emitter.assert_message("testcraft 3.14159")


def test_show_app_name_and_version(monkeypatch, capsys, app):
    """Test that the app name and version are shown during logging."""
    monkeypatch.setattr(sys, "argv", ["testcraft", "--verbosity=trace"])

    with pytest.raises(SystemExit):
        app.run()

    _, err = capsys.readouterr()
    assert f"Starting testcraft, version {app.app.version}" in err


@pytest.mark.parametrize("verbosity", list(craft_cli.EmitterMode))
def test_set_verbosity_from_env(monkeypatch, capsys, app, verbosity):
    """Test that the emitter verbosity is set from the environment."""
    monkeypatch.setattr(sys, "argv", ["testcraft"])
    monkeypatch.setenv("CRAFT_VERBOSITY_LEVEL", verbosity.name)

    with pytest.raises(SystemExit):
        app.run()

    _, err = capsys.readouterr()
    assert "testcraft [help]" in err
    assert craft_cli.emit._mode == verbosity


def test_set_verbosity_from_env_incorrect(monkeypatch, capsys, app):
    """Test that the emitter verbosity is using the default level when invalid."""
    monkeypatch.setattr(sys, "argv", ["testcraft"])
    monkeypatch.setenv("CRAFT_VERBOSITY_LEVEL", "incorrect")

    with pytest.raises(SystemExit):
        app.run()

    _, err = capsys.readouterr()
    assert "testcraft [help]" in err
    assert "Invalid verbosity level 'incorrect'" in err
    assert "Valid levels are: QUIET, BRIEF, VERBOSE, DEBUG, TRACE" in err
    assert craft_cli.emit._mode == craft_cli.EmitterMode.BRIEF


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

        def run(self, parsed_args: argparse.Namespace):
            return return_code

    monkeypatch.setattr(sys, "argv", ["testcraft", "pass"])

    app.add_command_group("test", [UnmanagedCommand])
    app.set_project(fake_project)

    check.equal(app.run(), return_code or 0)
    with check:
        emitter.assert_debug("Preparing application...")
    with check:
        emitter.assert_debug("Running testcraft pass on host")


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


class FakeCraftError(Exception):
    def __init__(self, *args: object) -> None:
        super().__init__(*args)
        self.details = "details"
        self.resolution = "resolution"
        self.reportable = True
        self.docs_url = "docs-url"
        self.doc_slug = "doc-slug"
        self.logpath_report = True
        self.retcode = 123


@pytest.mark.parametrize(
    ("exception", "transformed"),
    [
        pytest.param(
            KeyboardInterrupt(),
            craft_cli.CraftError("Interrupted.", retcode=130),
        ),
        pytest.param(
            craft_cli.CraftError("default"),
            craft_cli.CraftError("default"),
        ),
        pytest.param(
            craft_cli.CraftError(
                "message",
                details="details",
                resolution="resolution",
                docs_url="docs_url",
                reportable=False,
                logpath_report=False,
                retcode=-3,
                doc_slug="sluggy",
            ),
            craft_cli.CraftError(
                "message",
                details="details",
                resolution="resolution",
                docs_url="docs_url",
                reportable=False,
                logpath_report=False,
                retcode=-3,
                doc_slug="sluggy",
            ),
        ),
        pytest.param(
            craft_parts.PartsError("message", "details", "resolution", "doc-slug"),
            craft_cli.CraftError(
                "message",
                details="details",
                resolution="resolution",
                doc_slug="doc-slug",
            ),
        ),
        pytest.param(
            craft_providers.ProviderError("brief!", "details", "resolution"),
            craft_cli.CraftError(
                "brief!",
                details="details",
                resolution="resolution",
            ),
        ),
        pytest.param(
            craft_platforms.CraftPlatformsError(
                "brief!",
                "details",
                "resolution",
                docs_url="docs-url",
                doc_slug="doc_slug",
                logpath_report=False,
                reportable=False,
                retcode=-3,
            ),
            craft_cli.CraftError(
                "brief!",
                details="details",
                resolution="resolution",
                docs_url="docs-url",
                doc_slug="doc_slug",
                logpath_report=False,
                reportable=False,
                retcode=-3,
            ),
        ),
        pytest.param(
            FakeCraftError("message"),
            craft_cli.CraftError(
                "message",
                details="details",
                resolution="resolution",
                docs_url="docs-url",
                doc_slug="doc-slug",
                retcode=123,
            ),
        ),
    ],
)
@pytest.mark.usefixtures("production_mode")
def test_run_exception_transforms(
    emitter: craft_cli.pytest_plugin.RecordingEmitter,
    mocker,
    app: application.Application,
    exception,
    transformed: craft_cli.CraftError,
):
    mocker.patch.object(app, "_setup_logging")
    mocker.patch.object(app, "_configure_early_services")
    mocker.patch.object(app, "_initialize_craft_parts")
    mocker.patch.object(app, "_load_plugins")
    mocker.patch.object(app, "_run_inner", side_effect=exception)
    # Workaround for https://github.com/canonical/craft-cli/issues/162
    mock_error = mocker.patch.object(craft_cli.messages.Emitter, "error")

    assert app.run() == transformed.retcode

    mock_error.assert_called_once_with(transformed)


@pytest.mark.usefixtures("production_mode")
@pytest.mark.parametrize(
    "exception_cls", [Exception, KeyboardInterrupt, CraftError, ValueError]
)
def test_run_catches_exception(
    mocker: pytest_mock.MockerFixture,
    app: application.Application,
    exception_cls: type[BaseException],
):
    mocker.patch.object(app, "_run_inner", side_effect=exception_cls("Boo hoo"))

    # Check that it doesn't exit with success to know we caught an exception.
    assert app.run() != 0


@pytest.mark.parametrize("exception_cls", [BaseException, GeneratorExit, SystemExit])
def test_run_doesnt_catch_baseexception(
    mocker: pytest_mock.MockerFixture,
    app: application.Application,
    exception_cls: type[BaseException],
):
    mocker.patch.object(app, "_run_inner", side_effect=exception_cls("Boo hoo"))

    with pytest.raises(exception_cls):
        app.run()


@pytest.mark.parametrize(
    ("error", "return_code", "error_msg"),
    [
        (KeyboardInterrupt(), 130, "Interrupted.\n"),
        (craft_cli.CraftError("msg"), 1, "msg\n"),
        (craft_parts.PartsError("unable to pull"), 1, "unable to pull\n"),
        (
            craft_parts.errors.PluginBuildError(part_name="foo", plugin_name="python"),
            1,
            dedent(
                """\
                Failed to run the build script for part 'foo'.
                Recommended resolution: Check the build output and verify the project can work with the 'python' plugin.
            """
            ),
        ),
        (craft_providers.ProviderError("fail to launch"), 1, "fail to launch\n"),
        (Exception(), 70, "testcraft internal error: Exception()\n"),
        (
            craft_cli.ArgumentParsingError("Argument parsing error"),
            64,
            "Argument parsing error\n",
        ),
        (
            craft_cli.CraftError("Arbitrary return code", retcode=69),
            69,
            "Arbitrary return code\n",
        ),
    ],
)
@pytest.mark.usefixtures("emitter", "production_mode")
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
    _, err = capsys.readouterr()
    assert err.startswith(error_msg)


@pytest.mark.parametrize(
    ("error", "return_code", "error_msg"),
    [
        # PluginPullError does not have a docs_slug
        (
            craft_parts.errors.PluginPullError(part_name="foo"),
            1,
            dedent(
                """\
                Failed to run the pull script for part 'foo'.
                Full execution log:"""
            ),
        ),
        (
            craft_parts.errors.PluginBuildError(part_name="foo", plugin_name="python"),
            1,
            dedent(
                """\
                Failed to run the build script for part 'foo'.
                Recommended resolution: Check the build output and verify the project can work with the 'python' plugin.
                For more information, check out: http://testcraft.example/reference/plugins"""
            ),
        ),
    ],
)
def test_run_error_with_docs_url(
    monkeypatch,
    capsys,
    mock_dispatcher,
    app_metadata_docs,
    fake_services,
    fake_project,
    error,
    return_code,
    error_msg,
):
    app = FakeApplication(app_metadata_docs, fake_services)
    app.set_project(fake_project)
    mock_dispatcher.load_command.side_effect = error
    mock_dispatcher.pre_parse_args.return_value = {}
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull"])

    pytest_check.equal(app.run(), return_code)
    _, err = capsys.readouterr()
    assert err.startswith(error_msg), err


@pytest.mark.parametrize("error", [KeyError(), ValueError(), Exception()])
@pytest.mark.usefixtures("emitter", "debug_mode")
def test_run_error_debug(monkeypatch, mock_dispatcher, app, fake_project, error):
    app.set_project(fake_project)
    mock_dispatcher.load_command.side_effect = error
    mock_dispatcher.pre_parse_args.return_value = {}
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull"])

    with pytest.raises(error.__class__):
        app.run()


@pytest.mark.usefixtures("fake_project_file", "in_project_dir")
def test_work_dir_project_non_managed(monkeypatch, app_metadata, fake_services):
    monkeypatch.setenv(fake_services.ProviderClass.managed_mode_env_var, "0")
    # We want to use the real ProjectService here.
    fake_services.register("project", services.ProjectService)

    app = application.Application(app_metadata, fake_services)
    assert app._work_dir == pathlib.Path.cwd()

    project = app.get_project(build_for=get_host_architecture())

    # Make sure the project is loaded correctly (from the cwd)
    assert project is not None
    assert project.name == "full-project"
    assert project.version == "1.0.0.post64+git12345678"


@pytest.mark.usefixtures("fake_project_file")
def test_work_dir_project_managed(monkeypatch, app_metadata, fake_services):
    monkeypatch.setenv(fake_services.ProviderClass.managed_mode_env_var, "1")

    app = application.Application(app_metadata, fake_services)
    assert app._work_dir == pathlib.PosixPath("/root")

    project = app.get_project(build_for=get_host_architecture())

    # Make sure the project is loaded correctly (from the cwd)
    assert project is not None

    assert project.name == "full-project"
    assert project.version == "1.0.0.post64+git12345678"


@pytest.fixture
def environment_project(in_project_path):
    project_file = in_project_path / "testcraft.yaml"
    project_file.write_text(
        dedent(
            """\
            name: myproject
            version: 1.2.3
            base: ubuntu@24.04
            platforms:
              amd64:
              arm64:
              riscv64:
            parts:
              mypart:
                plugin: nil
                source-tag: v$CRAFT_PROJECT_VERSION
                build-environment:
                - BUILD_ON: $CRAFT_ARCH_BUILD_ON
                - BUILD_FOR: $CRAFT_ARCH_BUILD_FOR
            """
        )
    )

    return in_project_path


@pytest.mark.usefixtures("fake_project_file")
def test_get_project_current_dir(app):
    # Load a project file from the current directory
    project = app.get_project()

    # Check that it caches that project.
    assert app.get_project() is project, "Project file was not cached."


@pytest.mark.usefixtures("fake_project_file")
def test_get_project_all_platform(app):
    app.get_project(platform="arm64")


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


@pytest.fixture
def grammar_project_mini(tmp_path):
    """A project that builds on amd64 to riscv64 and s390x."""
    contents = dedent(
        """\
    name: myproject
    version: 1.0
    base: ubuntu@24.04
    platforms:
      riscv64:
        build-on: [amd64]
        build-for: [riscv64]
      s390x:
        build-on: [amd64]
        build-for: [s390x]
    parts:
      mypart:
        plugin: meson

        # grammar-only string
        source:
        - on amd64 to riscv64: on-amd64-to-riscv64
        - on amd64 to s390x: on-amd64-to-s390x
        - else: other

        # list of grammar and non-grammar data
        build-packages:
        - test-package
        - on amd64 to riscv64:
          - on-amd64-to-riscv64
        - on amd64 to s390x:
          - on-amd64-to-s390x

        # non-grammar data in a non-grammar keyword
        meson-parameters:
        - foo
        - bar
    """
    )
    project_file = tmp_path / "testcraft.yaml"
    project_file.write_text(contents)


def test_enable_features(app, mocker):
    calls = []

    def enable_features(*_args, **_kwargs):
        calls.append("enable-features")

    def register_plugins(*_args, **_kwargs):
        calls.append("register-plugins")

    mocker.patch.object(
        app, "_enable_craft_parts_features", side_effect=enable_features
    )
    mocker.patch.object(app, "_register_default_plugins", side_effect=register_plugins)

    with pytest.raises(SystemExit):
        app.run()

    # Check that features were enabled very early, before plugins are registered.
    assert calls == ["enable-features", "register-plugins"]


def test_emitter_docs_url(monkeypatch, mocker, app):
    """Test that the emitter is initialized with the correct url."""

    assert app.app.docs_url == "www.testcraft.example/docs/{version}"
    assert app.app.version == "3.14159"
    expected_url = "www.testcraft.example/docs/3.14159"

    spied_init = mocker.spy(emit, "init")

    monkeypatch.setattr(sys, "argv", ["testcraft"])
    with pytest.raises(SystemExit):
        app.run()

    assert spied_init.mock_calls[0].kwargs["docs_base_url"] == expected_url


class AppConfigCommand(AppCommand):
    name: str = "app-config"
    help_msg: str = "Help text"
    overview: str = "Overview"

    def fill_parser(self, parser: argparse.ArgumentParser) -> None:
        name = self._app.name
        parser.add_argument(
            "app-name",
            help=f"The name of the app, which is {name!r}.",
        )


@pytest.mark.usefixtures("emitter")
def test_app_config_in_help(
    monkeypatch,
    capsys,
    app,
):
    app.add_command_group("Test", [AppConfigCommand])
    monkeypatch.setattr(sys, "argv", ["testcraft", "app-config", "-h"])

    with pytest.raises(SystemExit):
        app.run()

    expected = "app-name:  The name of the app, which is 'testcraft'."
    _, err = capsys.readouterr()
    assert expected in err


@pytest.mark.parametrize(
    "help_args",
    [
        pytest.param(["--help"], id="simple help"),
        pytest.param(["help", "--all"], id="detailed help"),
    ],
)
@pytest.mark.usefixtures("emitter")
def test_doc_url_in_general_help(help_args, monkeypatch, capsys, app):
    """General help messages contain a link to the documentation."""
    monkeypatch.setattr(sys, "argv", ["testcraft", *help_args])

    with pytest.raises(SystemExit):
        app.run()

    expected = "For more information about testcraft, check out: www.testcraft.example/docs/3.14159\n\n"
    _, err = capsys.readouterr()
    assert err.endswith(expected)


@pytest.mark.usefixtures("emitter")
def test_doc_url_in_command_help(monkeypatch, capsys, app):
    """Command help messages contain a link to the command's doc page."""
    app.add_command_group("Test", [AppConfigCommand])
    monkeypatch.setattr(sys, "argv", ["testcraft", "app-config", "-h"])

    with pytest.raises(SystemExit):
        app.run()

    expected = "For more information, check out: www.testcraft.example/docs/3.14159/reference/commands/app-config\n\n"
    _, err = capsys.readouterr()
    assert err.endswith(expected)
