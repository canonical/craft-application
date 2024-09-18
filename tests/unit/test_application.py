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
import copy
import dataclasses
import importlib
import importlib.metadata
import logging
import pathlib
import re
import subprocess
import sys
import textwrap
from textwrap import dedent
from typing import Any
from unittest import mock

import craft_application
import craft_application.errors
import craft_cli
import craft_parts
import craft_providers
import pydantic
import pytest
import pytest_check
from craft_application import (
    application,
    commands,
    errors,
    models,
    secrets,
    services,
    util,
)
from craft_application.models import BuildInfo
from craft_application.util import (
    get_host_architecture,  # pyright: ignore[reportGeneralTypeIssues]
)
from craft_cli import emit
from craft_parts.plugins.plugins import PluginType
from craft_providers import bases
from overrides import override

EMPTY_COMMAND_GROUP = craft_cli.CommandGroup("FakeCommands", [])
BASIC_PROJECT_YAML = """
name: myproject
version: 1.0
base: ubuntu@24.04
platforms:
  arm64:
parts:
  mypart:
    plugin: nil
"""

FULL_PROJECT_YAML = """
name: myproject
version: 1.0
base: ubuntu@24.04
platforms:
  arm64:
parts:
  mypart:
    plugin: nil
    source: non-grammar-source
    source-checksum: on-amd64-to-riscv64-checksum
    source-branch: riscv64-branch
    source-commit: riscv64-commit
    source-depth: 1
    source-subdir: riscv64-subdir
    source-submodules:
      - riscv64-submodules-1
      - riscv64-submodules-2
    source-tag: riscv64-tag
    source-type: riscv64-type
    disable-parallel: true
    after:
      - riscv64-after
    organize:
      riscv64-organize-1: riscv64-organize-2
      riscv64-organize-3: riscv64-organize-4
    overlay:
      - riscv64-overlay-1
      - riscv64-overlay-2
    overlay-packages:
      - riscv64-overlay-1
      - riscv64-overlay-2
    overlay-script: riscv64-overlay-script
    stage:
      - riscv64-stage-1
      - riscv64-stage-2
    stage-snaps:
      - riscv64-snap-1
      - riscv64-snap-2
    stage-packages:
      - riscv64-package-1
      - riscv64-package-2
    prime:
      - riscv64-prime-1
      - riscv64-prime-2
    build-snaps:
      - riscv64-snap-1
      - riscv64-snap-2
    build-packages:
      - riscv64-package-1
      - riscv64-package-2
    build-environment:
      - MY_VAR: riscv64-value
      - MY_VAR2: riscv64-value2
    build-attributes:
      - rifcv64-attr-1
      - rifcv64-attr-2
    override-pull: riscv64-override-pull
    override-build: riscv64-override-build
    override-stage: riscv64-override-stage
    override-prime: riscv64-override-prime
    permissions:
      - path: riscv64-perm-1
        owner: 123
        group: 123
        mode: "777"
      - path: riscv64-perm-2
        owner: 456
        group: 456
        mode: "666"
"""

FULL_GRAMMAR_PROJECT_YAML = """
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
    plugin:
      - on amd64 to riscv64: nil
      - on amd64 to s390x: dump
    source:
      - on amd64 to s390x: on-amd64-to-s390x
      - on amd64 to riscv64: on-amd64-to-riscv64
    source-checksum:
      - on amd64 to riscv64: on-amd64-to-riscv64-checksum
      - on amd64 to s390x: on-amd64-to-s390x-checksum
    source-branch:
      - on amd64 to s390x: s390x-branch
      - on amd64 to riscv64: riscv64-branch
    source-commit:
      - on amd64 to riscv64: riscv64-commit
      - on amd64 to s390x: s390x-commit
    source-depth:
      - on amd64 to s390x: 2
      - on amd64 to riscv64: 1
    source-subdir:
      - on amd64 to riscv64: riscv64-subdir
      - on amd64 to s390x: s390x-subdir
    source-submodules:
      - on amd64 to s390x:
          - s390x-submodules-1
          - s390x-submodules-2
      - on amd64 to riscv64:
          - riscv64-submodules-1
          - riscv64-submodules-2
    source-tag:
      - on amd64 to riscv64: riscv64-tag
      - on amd64 to s390x: s390x-tag
    source-type:
      - on amd64 to s390x: s390x-type
      - on amd64 to riscv64: riscv64-type
    disable-parallel:
      - on amd64 to riscv64: true
      - on amd64 to s390x: false
    after:
      - on amd64 to s390x:
        - s390x-after
      - on amd64 to riscv64:
        - riscv64-after
    organize:
        - on amd64 to riscv64:
            riscv64-organize-1: riscv64-organize-2
            riscv64-organize-3: riscv64-organize-4
        - on amd64 to s390x:
            s390x-organize-1: s390x-organize-2
            s390x-organize-3: s390x-organize-4
    overlay:
      - on amd64 to s390x:
        - s390x-overlay-1
        - s390x-overlay-2
      - on amd64 to riscv64:
        - riscv64-overlay-1
        - riscv64-overlay-2
    overlay-packages:
      - on amd64 to riscv64:
        - riscv64-overlay-1
        - riscv64-overlay-2
      - on amd64 to s390x:
        - s390x-overlay-1
        - s390x-overlay-2
    overlay-script:
        - on amd64 to s390x: s390x-overlay-script
        - on amd64 to riscv64: riscv64-overlay-script
    stage:
      - on amd64 to riscv64:
        - riscv64-stage-1
        - riscv64-stage-2
      - on amd64 to s390x:
        - s390x-stage-1
        - s390x-stage-2
    stage-snaps:
      - on amd64 to s390x:
        - s390x-snap-1
        - s390x-snap-2
      - on amd64 to riscv64:
        - riscv64-snap-1
        - riscv64-snap-2
    stage-packages:
      - on amd64 to riscv64:
        - riscv64-package-1
        - riscv64-package-2
      - on amd64 to s390x:
        - s390x-package-1
        - s390x-package-2
    prime:
      - on amd64 to s390x:
        - s390x-prime-1
        - s390x-prime-2
      - on amd64 to riscv64:
        - riscv64-prime-1
        - riscv64-prime-2
    build-snaps:
      - on amd64 to riscv64:
        - riscv64-snap-1
        - riscv64-snap-2
      - on amd64 to s390x:
        - s390x-snap-1
        - s390x-snap-2
    build-packages:
      - on amd64 to s390x:
        - s390x-package-1
        - s390x-package-2
      - on amd64 to riscv64:
        - riscv64-package-1
        - riscv64-package-2
    build-environment:
      - on amd64 to riscv64:
          - MY_VAR: riscv64-value
          - MY_VAR2: riscv64-value2
      - on amd64 to s390x:
          - MY_VAR: s390x-value
          - MY_VAR2: s390x-value2
    build-attributes:
      - on amd64 to s390x:
        - s390x-attr-1
        - s390x-attr-2
      - on amd64 to riscv64:
        - rifcv64-attr-1
        - rifcv64-attr-2
    override-pull:
      - on amd64 to riscv64: riscv64-override-pull
      - on amd64 to s390x: s390x-override-pull
    override-build:
      - on amd64 to s390x: s390x-override-build
      - on amd64 to riscv64: riscv64-override-build
    override-stage:
      - on amd64 to riscv64: riscv64-override-stage
      - on amd64 to s390x: s390x-override-stage
    override-prime:
      - on amd64 to s390x: s390x-override-prime
      - on amd64 to riscv64: riscv64-override-prime
    permissions:
      - on amd64 to riscv64:
        - path: riscv64-perm-1
          owner: 123
          group: 123
          mode: "777"
        - path: riscv64-perm-2
          owner: 456
          group: 456
          mode: "666"
      - on amd64 to s390x:
        - path: s390x-perm-1
          owner: 123
          group: 123
          mode: "666"
        - path: s390x-perm-2
          owner: 456
          group: 456
          mode: "777"
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


@pytest.fixture
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


def test_run_managed_success(mocker, app, fake_project, fake_build_plan):
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services.provider = mock_provider
    app.project = fake_project
    app._build_plan = fake_build_plan
    mock_pause = mocker.spy(craft_cli.emit, "pause")
    arch = get_host_architecture()

    app.run_managed(None, arch)

    assert (
        mock.call(
            fake_build_plan[0],
            work_dir=mock.ANY,
        )
        in mock_provider.instance.mock_calls
    )
    mock_pause.assert_called_once()


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


def test_run_managed_empty_plan(app, fake_project):
    app.set_project(fake_project)

    app._build_plan = []
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
@pytest.mark.usefixtures("emitter")
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

    pytest_check.is_not_none(fake_services.project)
    pytest_check.is_not_none(app.project)


def test_fails_without_project(
    monkeypatch, capsys, tmp_path, app_metadata, fake_services
):
    monkeypatch.setattr(sys, "argv", ["testcraft", "prime"])

    app = FakeApplication(app_metadata, fake_services)
    app.project_dir = tmp_path

    fake_services.project = None

    assert app.run() == 66  # noqa: PLR2004

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


@pytest.mark.parametrize(
    ("params", "expected_call"),
    [
        ([], mock.call(None, None)),
        (["--platform=s390x"], mock.call("s390x", None)),
        (
            ["--platform", get_host_architecture()],
            mock.call(get_host_architecture(), None),
        ),
        (
            ["--build-for", get_host_architecture()],
            mock.call(None, get_host_architecture()),
        ),
        (["--build-for", "s390x"], mock.call(None, "s390x")),
        (["--platform", "s390x,riscv64"], mock.call("s390x", None)),
        (["--build-for", "s390x,riscv64"], mock.call(None, "s390x")),
    ],
)
def test_run_passes_platforms(
    monkeypatch, app, fake_project, mocker, params, expected_call
):
    mocker.patch.object(app, "get_project", return_value=fake_project)
    app.run_managed = mock.Mock(return_value=False)
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull", *params])

    pytest_check.equal(app.run(), 0)

    assert app.run_managed.mock_calls == [expected_call]


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
@pytest.mark.usefixtures("emitter")
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
                For more information, check out: http://craft-app.com/reference/plugins.html
                Full execution log:"""
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
    assert err.startswith(error_msg)


@pytest.mark.parametrize("error", [KeyError(), ValueError(), Exception()])
@pytest.mark.usefixtures("emitter")
def test_run_error_debug(monkeypatch, mock_dispatcher, app, fake_project, error):
    app.set_project(fake_project)
    mock_dispatcher.load_command.side_effect = error
    mock_dispatcher.pre_parse_args.return_value = {}
    monkeypatch.setattr(sys, "argv", ["testcraft", "pull"])
    monkeypatch.setenv("CRAFT_DEBUG", "1")

    with pytest.raises(error.__class__):
        app.run()


_base = bases.BaseName("", "")
_pc_on_amd64_for_amd64 = BuildInfo(
    platform="pc", build_on="amd64", build_for="amd64", base=_base
)
_pc_on_amd64_for_i386 = BuildInfo(
    platform="legacy-pc", build_on="amd64", build_for="i386", base=_base
)
_amd64_on_amd64_for_amd64 = BuildInfo(
    platform="amd64", build_on="amd64", build_for="amd64", base=_base
)
_i386_on_amd64_for_i386 = BuildInfo(
    platform="i386", build_on="amd64", build_for="i386", base=_base
)
_i386_on_i386_for_i386 = BuildInfo(
    platform="i386", build_on="i386", build_for="i386", base=_base
)


@pytest.mark.parametrize(
    ("_id", "plan", "platform", "build_for", "host_arch", "result"),
    [
        (0, [_pc_on_amd64_for_amd64], None, None, "amd64", [_pc_on_amd64_for_amd64]),
        (1, [_pc_on_amd64_for_amd64], "pc", None, "amd64", [_pc_on_amd64_for_amd64]),
        (2, [_pc_on_amd64_for_amd64], "legacy-pc", None, "amd64", []),
        (3, [_pc_on_amd64_for_amd64], None, "amd64", "amd64", [_pc_on_amd64_for_amd64]),
        (4, [_pc_on_amd64_for_amd64], "pc", "amd64", "amd64", [_pc_on_amd64_for_amd64]),
        (5, [_pc_on_amd64_for_amd64], "legacy-pc", "amd64", "amd64", []),
        (6, [_pc_on_amd64_for_amd64], None, "i386", "amd64", []),
        (7, [_pc_on_amd64_for_amd64], None, "amd64", "i386", []),
        (
            8,
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            None,
            "i386",
            "amd64",
            [_pc_on_amd64_for_i386],
        ),
        (
            9,
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            "pc",
            "amd64",
            "i386",
            [],
        ),
        (
            10,
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            "legacy-pc",
            "i386",
            "amd64",
            [_pc_on_amd64_for_i386],
        ),
        (11, [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386], None, "i386", "i386", []),
        (12, [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386], None, None, "i386", []),
        (
            13,
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            "legacy-pc",
            None,
            "i386",
            [],
        ),
        (
            14,
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            None,
            None,
            "amd64",
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
        ),
        (
            15,
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            "legacy-pc",
            None,
            "amd64",
            [_pc_on_amd64_for_i386],
        ),
        (
            16,
            [_pc_on_amd64_for_amd64, _amd64_on_amd64_for_amd64],
            None,
            "amd64",
            "amd64",
            [_amd64_on_amd64_for_amd64],
        ),
        (
            17,
            [_pc_on_amd64_for_amd64, _amd64_on_amd64_for_amd64],
            "amd64",
            None,
            "amd64",
            [_amd64_on_amd64_for_amd64],
        ),
        (
            18,
            [_pc_on_amd64_for_amd64, _amd64_on_amd64_for_amd64],
            "amd64",
            "amd64",
            "amd64",
            [_amd64_on_amd64_for_amd64],
        ),
        (
            19,
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386],
            None,
            "i386",
            "amd64",
            [_i386_on_amd64_for_i386],
        ),
        (
            20,
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386],
            "amd64",
            None,
            "amd64",
            [],
        ),
        (
            21,
            [
                _pc_on_amd64_for_amd64,
                _amd64_on_amd64_for_amd64,
                _i386_on_amd64_for_i386,
            ],
            None,
            "amd64",
            "amd64",
            [_amd64_on_amd64_for_amd64],
        ),
        (
            22,
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386],
            "i386",
            "i386",
            "amd64",
            [_i386_on_amd64_for_i386],
        ),
        (
            23,
            [
                _pc_on_amd64_for_amd64,
                _amd64_on_amd64_for_amd64,
                _i386_on_amd64_for_i386,
            ],
            None,
            "i386",
            "amd64",
            [_i386_on_amd64_for_i386],
        ),
        (
            24,
            [_pc_on_amd64_for_amd64, _amd64_on_amd64_for_amd64],
            None,
            "i386",
            "amd64",
            [],
        ),
        (
            25,
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386, _i386_on_i386_for_i386],
            "amd64",
            None,
            "amd64",
            [],
        ),
        (
            26,
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386, _i386_on_i386_for_i386],
            "amd64",
            None,
            "i386",
            [],
        ),
        (
            27,
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386, _i386_on_i386_for_i386],
            "i386",
            None,
            "amd64",
            [_i386_on_amd64_for_i386],
        ),
        (
            28,
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386, _i386_on_i386_for_i386],
            "i386",
            None,
            "i386",
            [_i386_on_i386_for_i386],
        ),
        (
            29,
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386, _i386_on_i386_for_i386],
            None,
            "i386",
            "i386",
            [_i386_on_i386_for_i386],
        ),
        (
            30,
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386, _i386_on_i386_for_i386],
            "i386",
            None,
            None,
            [_i386_on_amd64_for_i386, _i386_on_i386_for_i386],
        ),
    ],
)
@pytest.mark.usefixtures("_id")
def test_filter_plan(mocker, plan, platform, build_for, host_arch, result):
    mocker.patch("craft_application.util.get_host_architecture", return_value=host_arch)
    assert application.filter_plan(plan, platform, build_for, host_arch) == result


@pytest.fixture
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


@pytest.fixture
def environment_project(monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_path = project_dir / "testcraft.yaml"
    project_path.write_text(
        dedent(
            """
        name: myproject
        version: 1.2.3
        base: ubuntu@24.04
        platforms:
          arm64:
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
    monkeypatch.chdir(project_dir)

    return project_path


def test_expand_environment_build_for_all(
    monkeypatch, app_metadata, tmp_path, fake_services, emitter
):
    """Expand build-for to the host arch when build-for is 'all'."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_path = project_dir / "testcraft.yaml"
    project_path.write_text(
        dedent(
            f"""\
            name: myproject
            version: 1.2.3
            base: ubuntu@24.04
            platforms:
              platform1:
                build-on: [{util.get_host_architecture()}]
                build-for: [all]
            parts:
              mypart:
                plugin: nil
                build-environment:
                  - BUILD_ON: $CRAFT_ARCH_BUILD_ON
                  - BUILD_FOR: $CRAFT_ARCH_BUILD_FOR
        """
        )
    )
    monkeypatch.chdir(project_dir)

    app = application.Application(app_metadata, fake_services)
    project = app.get_project()

    # Make sure the project is loaded correctly (from the cwd)
    assert project is not None
    assert project.parts["mypart"]["build-environment"] == [
        {"BUILD_ON": util.get_host_architecture()},
        {"BUILD_FOR": util.get_host_architecture()},
    ]
    emitter.assert_debug(
        "Expanding environment variables with the host architecture "
        f"{util.get_host_architecture()!r} as the build-for architecture "
        "because 'all' was specified."
    )


@pytest.mark.usefixtures("environment_project")
def test_application_expand_environment(app_metadata, fake_services):
    app = application.Application(app_metadata, fake_services)
    project = app.get_project(build_for=get_host_architecture())

    # Make sure the project is loaded correctly (from the cwd)
    assert project is not None
    assert project.parts["mypart"]["source-tag"] == "v1.2.3"
    assert project.parts["mypart"]["build-environment"] == [
        {"BUILD_ON": util.get_host_architecture()},
        {"BUILD_FOR": util.get_host_architecture()},
    ]


@pytest.fixture
def build_secrets_project(monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_path = project_dir / "testcraft.yaml"
    project_path.write_text(
        dedent(
            """
        name: myproject
        version: 1.2.3
        base: ubuntu@24.04
        platforms:
          arm64:
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
    app.get_project(platform="arm64")


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
    _ = app.get_project(build_for="s390x")

    assert app.build_on == util.get_host_architecture()
    assert app.build_for == "s390x"


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


@pytest.fixture
def non_grammar_project_full(tmp_path):
    """A project that builds on amd64 to riscv64."""
    project_file = tmp_path / "testcraft.yaml"
    project_file.write_text(FULL_PROJECT_YAML)


@pytest.fixture
def grammar_project_full(tmp_path):
    """A project that builds on amd64 to riscv64 and s390x."""
    project_file = tmp_path / "testcraft.yaml"
    project_file.write_text(FULL_GRAMMAR_PROJECT_YAML)


@pytest.fixture
def non_grammar_build_plan(mocker):
    """A build plan to build on amd64 to riscv64."""
    host_arch = "amd64"
    base = util.get_host_base()
    build_plan = [
        models.BuildInfo(
            "platform-riscv64",
            host_arch,
            "riscv64",
            base,
        )
    ]

    mocker.patch.object(models.BuildPlanner, "get_build_plan", return_value=build_plan)


@pytest.fixture
def grammar_build_plan(mocker):
    """A build plan to build on amd64 to riscv64 and s390x."""
    host_arch = "amd64"
    base = util.get_host_base()
    build_plan = [
        models.BuildInfo(
            f"platform-{build_for}",
            host_arch,
            build_for,
            base,
        )
        for build_for in ("riscv64", "s390x")
    ]

    mocker.patch.object(models.BuildPlanner, "get_build_plan", return_value=build_plan)


@pytest.fixture
def grammar_app_mini(
    tmp_path,
    grammar_project_mini,  # noqa: ARG001
    grammar_build_plan,  # noqa: ARG001
    app_metadata,
    fake_services,
):
    app = application.Application(app_metadata, fake_services)
    app.project_dir = tmp_path

    return app


@pytest.fixture
def non_grammar_app_full(
    tmp_path,
    non_grammar_project_full,  # noqa: ARG001
    non_grammar_build_plan,  # noqa: ARG001
    app_metadata,
    fake_services,
):
    app = application.Application(app_metadata, fake_services)
    app.project_dir = tmp_path

    return app


@pytest.fixture
def grammar_app_full(
    tmp_path,
    grammar_project_full,  # noqa: ARG001
    grammar_build_plan,  # noqa: ARG001
    app_metadata,
    fake_services,
):
    app = application.Application(app_metadata, fake_services)
    app.project_dir = tmp_path

    return app


def test_process_grammar_build_for(grammar_app_mini):
    """Test that a provided build-for is used to process the grammar."""
    project = grammar_app_mini.get_project(build_for="s390x")
    assert project.parts["mypart"]["source"] == "on-amd64-to-s390x"
    assert project.parts["mypart"]["build-packages"] == [
        "test-package",
        "on-amd64-to-s390x",
    ]


def test_process_grammar_to_all(tmp_path, app_metadata, fake_services):
    """Test that 'to all' is a valid grammar statement."""
    contents = dedent(
        f"""\
        name: myproject
        version: 1.0
        base: ubuntu@24.04
        platforms:
          myplatform:
            build-on: [{util.get_host_architecture()}]
            build-for: [all]
        parts:
          mypart:
            plugin: nil
            build-packages:
            - test-package
            - on {util.get_host_architecture()} to all:
              - on-host-to-all
            - to all:
              - to-all
            - on {util.get_host_architecture()} to s390x:
              - on-host-to-s390x
            - to s390x:
              - on-amd64-to-s390x
        """
    )
    project_file = tmp_path / "testcraft.yaml"
    project_file.write_text(contents)
    app = application.Application(app_metadata, fake_services)
    app.project_dir = tmp_path

    project = app.get_project()

    assert project.parts["mypart"]["build-packages"] == [
        "test-package",
        "on-host-to-all",
        "to-all",
    ]


def test_process_grammar_platform(grammar_app_mini):
    """Test that a provided platform is used to process the grammar."""
    project = grammar_app_mini.get_project(platform="platform-riscv64")
    assert project.parts["mypart"]["source"] == "on-amd64-to-riscv64"
    assert project.parts["mypart"]["build-packages"] == [
        "test-package",
        "on-amd64-to-riscv64",
    ]


def test_process_grammar_non_grammar(grammar_app_mini):
    """Non-grammar keywords should not be modified."""
    project = grammar_app_mini.get_project(platform="platform-riscv64")

    assert project.parts["mypart"]["meson-parameters"] == ["foo", "bar"]


def test_process_grammar_default(grammar_app_mini):
    """Test that if nothing is provided the first BuildInfo is used by the grammar."""
    project = grammar_app_mini.get_project()
    assert project.parts["mypart"]["source"] == "on-amd64-to-riscv64"
    assert project.parts["mypart"]["build-packages"] == [
        "test-package",
        "on-amd64-to-riscv64",
    ]


def test_process_grammar_no_match(grammar_app_mini, mocker):
    """Test that if the build plan is empty, the grammar uses the host as target arch."""
    mocker.patch("craft_application.util.get_host_architecture", return_value="i386")
    project = grammar_app_mini.get_project()

    assert project.parts["mypart"]["source"] == "other"
    assert project.parts["mypart"]["build-packages"] == ["test-package"]


class FakeApplicationWithYamlTransform(FakeApplication):
    """Application class that adds data in `_extra_yaml_transform`."""

    @override
    def _extra_yaml_transform(
        self,
        yaml_data: dict[str, Any],
        *,
        build_on: str,  # noqa: ARG002 (Unused method argument)
        build_for: str | None,  # noqa: ARG002 (Unused method argument)
    ) -> dict[str, Any]:
        # do not modify the dict passed in
        new_yaml_data = copy.deepcopy(yaml_data)
        new_yaml_data["parts"] = {
            "mypart": {
                "plugin": "nil",
                # advanced grammar
                "build-packages": [
                    "test-package",
                    {"to riscv64": "riscv64-package"},
                    {"to s390x": "s390x-package"},
                ],
                "build-environment": [
                    # project variables
                    {"hello": "$CRAFT_ARCH_BUILD_ON"},
                    # build secrets
                    {"MY_VAR": "$(HOST_SECRET:echo ${SECRET_VAR})"},
                ],
            }
        }

        return new_yaml_data


@pytest.mark.enable_features("build_secrets")
def test_process_yaml_from_extra_transform(
    app_metadata, fake_services, tmp_path, monkeypatch
):
    """Test that grammar is applied on data from `_extra_yaml_transform`."""
    monkeypatch.setenv("SECRET_VAR", "secret-value")
    project_file = tmp_path / "testcraft.yaml"
    project_file.write_text(BASIC_PROJECT_YAML)

    app = FakeApplicationWithYamlTransform(app_metadata, fake_services)
    app.project_dir = tmp_path
    project = app.get_project(build_for="riscv64")

    # process grammar
    assert project.parts["mypart"]["build-packages"] == [
        "test-package",
        "riscv64-package",
    ]
    assert project.parts["mypart"]["build-environment"] == [
        # evaluate project variables
        {"hello": get_host_architecture()},
        # render secrets
        {"MY_VAR": "secret-value"},
    ]


class FakePartitionsApplication(FakeApplication):
    """A partition using FakeApplication."""

    @override
    def _setup_partitions(self, yaml_data) -> list[str]:
        _ = yaml_data
        return ["default", "mypartition"]


@pytest.fixture
def environment_partitions_project(monkeypatch, tmp_path):
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    project_path = project_dir / "testcraft.yaml"
    project_path.write_text(
        dedent(
            """
        name: myproject
        version: 1.2.3
        base: ubuntu@24.04
        platforms:
          arm64:
        parts:
          mypart:
            plugin: nil
            source-tag: v$CRAFT_PROJECT_VERSION
            override-stage: |
              touch $CRAFT_STAGE/default
              touch $CRAFT_MYPARTITION_STAGE/partition
            override-prime: |
              touch $CRAFT_PRIME/default
              touch $CRAFT_MYPARTITION_PRIME/partition
        """
        )
    )
    monkeypatch.chdir(project_dir)

    return project_path


@pytest.mark.usefixtures("enable_partitions")
@pytest.mark.usefixtures("environment_partitions_project")
def test_partition_application_expand_environment(app_metadata, fake_services):
    app = FakePartitionsApplication(app_metadata, fake_services)
    project = app.get_project(build_for=get_host_architecture())

    assert craft_parts.Features().enable_partitions is True
    # Make sure the project is loaded correctly (from the cwd)
    assert project is not None
    assert project.parts["mypart"]["source-tag"] == "v1.2.3"
    assert project.parts["mypart"]["override-stage"] == dedent(
        f"""\
        touch {app.project_dir}/stage/default
        touch {app.project_dir}/partitions/mypartition/stage/partition
    """
    )
    assert project.parts["mypart"]["override-prime"] == dedent(
        f"""\
        touch {app.project_dir}/prime/default
        touch {app.project_dir}/partitions/mypartition/prime/partition
    """
    )


@pytest.mark.usefixtures("enable_overlay")
def test_process_non_grammar_full(non_grammar_app_full):
    """Test that the non-grammar project is processed correctly.

    The following fields are not included due to not able to be tested in this context:
    - parse-info
    """
    project = non_grammar_app_full.get_project()
    assert project.parts["mypart"]["plugin"] == "nil"
    assert project.parts["mypart"]["source"] == "non-grammar-source"
    assert project.parts["mypart"]["source-checksum"] == "on-amd64-to-riscv64-checksum"
    assert project.parts["mypart"]["source-branch"] == "riscv64-branch"
    assert project.parts["mypart"]["source-commit"] == "riscv64-commit"
    assert project.parts["mypart"]["source-depth"] == 1
    assert project.parts["mypart"]["source-subdir"] == "riscv64-subdir"
    assert project.parts["mypart"]["source-submodules"] == [
        "riscv64-submodules-1",
        "riscv64-submodules-2",
    ]
    assert project.parts["mypart"]["source-tag"] == "riscv64-tag"
    assert project.parts["mypart"]["source-type"] == "riscv64-type"
    assert project.parts["mypart"]["disable-parallel"] is True
    assert project.parts["mypart"]["after"] == ["riscv64-after"]
    assert project.parts["mypart"]["organize"] == {
        "riscv64-organize-1": "riscv64-organize-2",
        "riscv64-organize-3": "riscv64-organize-4",
    }
    assert project.parts["mypart"]["overlay"] == [
        "riscv64-overlay-1",
        "riscv64-overlay-2",
    ]
    assert project.parts["mypart"]["overlay-script"] == "riscv64-overlay-script"
    assert project.parts["mypart"]["stage"] == ["riscv64-stage-1", "riscv64-stage-2"]
    assert project.parts["mypart"]["stage-snaps"] == [
        "riscv64-snap-1",
        "riscv64-snap-2",
    ]
    assert project.parts["mypart"]["stage-packages"] == [
        "riscv64-package-1",
        "riscv64-package-2",
    ]
    assert project.parts["mypart"]["prime"] == ["riscv64-prime-1", "riscv64-prime-2"]
    assert project.parts["mypart"]["build-snaps"] == [
        "riscv64-snap-1",
        "riscv64-snap-2",
    ]
    assert project.parts["mypart"]["build-packages"] == [
        "riscv64-package-1",
        "riscv64-package-2",
    ]
    assert project.parts["mypart"]["build-environment"] == [
        {"MY_VAR": "riscv64-value"},
        {"MY_VAR2": "riscv64-value2"},
    ]
    assert project.parts["mypart"]["build-attributes"] == [
        "rifcv64-attr-1",
        "rifcv64-attr-2",
    ]
    assert project.parts["mypart"]["override-pull"] == "riscv64-override-pull"
    assert project.parts["mypart"]["override-build"] == "riscv64-override-build"
    assert project.parts["mypart"]["override-stage"] == "riscv64-override-stage"
    assert project.parts["mypart"]["override-prime"] == "riscv64-override-prime"
    assert project.parts["mypart"]["permissions"] == [
        {"path": "riscv64-perm-1", "owner": 123, "group": 123, "mode": "777"},
        {"path": "riscv64-perm-2", "owner": 456, "group": 456, "mode": "666"},
    ]


@pytest.mark.usefixtures("enable_overlay")
def test_process_grammar_full(grammar_app_full):
    """Test that the nearly all grammar is processed correctly.

    The following fields are not included due to not able to be tested in this context:
    - parse-info
    """
    project = grammar_app_full.get_project()
    assert project.parts["mypart"]["plugin"] == "nil"
    assert project.parts["mypart"]["source"] == "on-amd64-to-riscv64"
    assert project.parts["mypart"]["source-checksum"] == "on-amd64-to-riscv64-checksum"
    assert project.parts["mypart"]["source-branch"] == "riscv64-branch"
    assert project.parts["mypart"]["source-commit"] == "riscv64-commit"
    assert project.parts["mypart"]["source-depth"] == 1
    assert project.parts["mypart"]["source-subdir"] == "riscv64-subdir"
    assert project.parts["mypart"]["source-submodules"] == [
        "riscv64-submodules-1",
        "riscv64-submodules-2",
    ]
    assert project.parts["mypart"]["source-tag"] == "riscv64-tag"
    assert project.parts["mypart"]["source-type"] == "riscv64-type"
    assert project.parts["mypart"]["disable-parallel"] is True
    assert project.parts["mypart"]["after"] == ["riscv64-after"]
    assert project.parts["mypart"]["organize"] == {
        "riscv64-organize-1": "riscv64-organize-2",
        "riscv64-organize-3": "riscv64-organize-4",
    }
    assert project.parts["mypart"]["overlay"] == [
        "riscv64-overlay-1",
        "riscv64-overlay-2",
    ]
    assert project.parts["mypart"]["overlay-script"] == "riscv64-overlay-script"
    assert project.parts["mypart"]["stage"] == ["riscv64-stage-1", "riscv64-stage-2"]
    assert project.parts["mypart"]["stage-snaps"] == [
        "riscv64-snap-1",
        "riscv64-snap-2",
    ]
    assert project.parts["mypart"]["stage-packages"] == [
        "riscv64-package-1",
        "riscv64-package-2",
    ]
    assert project.parts["mypart"]["prime"] == ["riscv64-prime-1", "riscv64-prime-2"]
    assert project.parts["mypart"]["build-snaps"] == [
        "riscv64-snap-1",
        "riscv64-snap-2",
    ]
    assert project.parts["mypart"]["build-packages"] == [
        "riscv64-package-1",
        "riscv64-package-2",
    ]
    assert project.parts["mypart"]["build-environment"] == [
        {"MY_VAR": "riscv64-value"},
        {"MY_VAR2": "riscv64-value2"},
    ]
    assert project.parts["mypart"]["build-attributes"] == [
        "rifcv64-attr-1",
        "rifcv64-attr-2",
    ]
    assert project.parts["mypart"]["override-pull"] == "riscv64-override-pull"
    assert project.parts["mypart"]["override-build"] == "riscv64-override-build"
    assert project.parts["mypart"]["override-stage"] == "riscv64-override-stage"
    assert project.parts["mypart"]["override-prime"] == "riscv64-override-prime"
    assert project.parts["mypart"]["permissions"] == [
        {"path": "riscv64-perm-1", "owner": 123, "group": 123, "mode": "777"},
        {"path": "riscv64-perm-2", "owner": 456, "group": 456, "mode": "666"},
    ]


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


class MyRaisingPlanner(models.BuildPlanner):
    value1: int
    value2: str

    @pydantic.field_validator("value1", mode="after")
    @classmethod
    def _validate_value1(cls, v):
        raise ValueError(f"Bad value1: {v}")

    @pydantic.field_validator("value2", mode="after")
    @classmethod
    def _validate_value(cls, v):
        raise ValueError(f"Bad value2: {v}")

    @override
    def get_build_plan(self) -> list[BuildInfo]:
        return []


def test_build_planner_errors(tmp_path, monkeypatch, fake_services):
    monkeypatch.chdir(tmp_path)
    app_metadata = craft_application.AppMetadata(
        "testcraft",
        "A fake app for testing craft-application",
        BuildPlannerClass=MyRaisingPlanner,
        source_ignore_patterns=["*.snap", "*.charm", "*.starcraft"],
    )
    app = FakeApplication(app_metadata, fake_services)
    project_contents = textwrap.dedent(
        """\
        name: my-project
        base: ubuntu@24.04
        value1: 10
        value2: "banana"
        platforms:
          amd64:
        """
    ).strip()
    project_path = tmp_path / "testcraft.yaml"
    project_path.write_text(project_contents)

    with pytest.raises(errors.CraftValidationError) as err:
        app.get_project()

    expected = (
        "Bad testcraft.yaml content:\n"
        "- bad value1: 10 (in field 'value1')\n"
        "- bad value2: banana (in field 'value2')"
    )
    assert str(err.value) == expected


def test_emitter_docs_url(monkeypatch, mocker, app):
    """Test that the emitter is initialized with the correct url."""

    assert app.app.docs_url == "www.craft-app.com/docs/{version}"
    assert app.app.version == "3.14159"
    expected_url = "www.craft-app.com/docs/3.14159"

    spied_init = mocker.spy(emit, "init")

    monkeypatch.setattr(sys, "argv", ["testcraft"])
    with pytest.raises(SystemExit):
        app.run()

    assert spied_init.mock_calls[0].kwargs["docs_base_url"] == expected_url
