# This file is part of craft_application.
#
# Copyright 2025 Canonical Ltd.
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

"""Unit tests for craft-application app plugins."""

import argparse
import os
import sys
import textwrap
from importlib.metadata import Distribution, DistributionFinder
from types import ModuleType
from typing import cast

import pytest
from craft_cli import emit
from overrides import override

from craft_application import (
    Application,
    AppService,
    commands,
    services,
)

FAKE_APP = "boopcraft"
PLUGIN_GROUP_NAME = "craft_application_plugins.application"
PLUGIN_ENTRY_POINT_NAME = f"{FAKE_APP}_plugin"
PLUGIN_MODULE_NAME = f"{FAKE_APP}_module"


def configure(app: Application) -> None:
    assert app.services.get("fake"), "Fake service is not provided by app."


@pytest.fixture
def entry_points_faker():
    # Save unmodified sys.modules
    og_modules = sys.modules

    def entry_points_faker(
        entry_points: list[tuple[str, str, callable]] | None = None,  # type: ignore[reportGeneralTypeIssues]
    ):
        # All go under this group for our purposes
        entry_points_txt = f"[{PLUGIN_GROUP_NAME}]\n"

        if not entry_points:
            # Simple case
            entry_points = [
                (
                    PLUGIN_ENTRY_POINT_NAME,
                    PLUGIN_MODULE_NAME,
                    configure,
                )
            ]

        for entry_point_name, module_name, configure_func in entry_points:
            entry_points_txt += f"{entry_point_name} = {module_name}\n"
            module = ModuleType(module_name)
            module.configure = configure_func  # type: ignore[reportAttributeAccessIssue]
            sys.modules[module_name] = module

        class FakeDistribution(Distribution):
            def __init__(self, entry_points):
                self._entry_points = entry_points

            def read_text(self, filename):
                if filename == "entry_points.txt":
                    return self._entry_points
                # These cases ensure things don't explode inside importlib
                if filename == "METADATA":
                    return "Name: wef"
                return ""

            def locate_file(self, path):
                raise NotImplementedError

        class FakeDistributionFinder(DistributionFinder):
            def find_distributions(self, context=None):
                return [FakeDistribution(entry_points_txt)]

        # Set up the fakery
        sys.meta_path.append(FakeDistributionFinder)  # type: ignore[reportArgumentType]

    yield entry_points_faker

    # Restore environment
    sys.modules = og_modules
    sys.meta_path.pop()


@pytest.fixture
def fake_service():
    class FakeService(AppService): ...

    services.ServiceFactory.register("fake", FakeService)


def test_app_no_plugins(monkeypatch, app_metadata, fake_services, emitter):
    app = Application(app_metadata, fake_services)
    app._setup_logging()
    app._load_plugins()
    with pytest.raises(AssertionError):
        emitter.assert_debug("Loading app plugin .*", regex=True)


@pytest.mark.usefixtures("fake_project_file")
def test_app_plugin_load_fails(
    app_metadata, fake_service, fake_services, emitter, entry_points_faker
):
    def broken_configure(app: Application):
        raise Exception("Help!")  # noqa: TRY002

    entry_points_faker(
        [(PLUGIN_ENTRY_POINT_NAME, PLUGIN_MODULE_NAME, broken_configure)]
    )
    app = Application(app_metadata, fake_services)
    app._setup_logging()

    # Should not raise an exception
    app._load_plugins()

    emitter.assert_debug(f"Loading app plugin {PLUGIN_ENTRY_POINT_NAME}")
    emitter.assert_progress(
        f"Failed to load plugin {PLUGIN_ENTRY_POINT_NAME}",
        permanent=True,
    )
    for msg in emitter.interactions:
        if msg.args[0] == "debug" and msg.args[1].startswith("Traceback"):
            assert msg.args[1].endswith("Exception: Help!\n")
            return
    raise AssertionError("Didn't find traceback")


@pytest.mark.usefixtures("fake_project_file")
def test_app_plugin_loaded(
    app_metadata, fake_service, fake_services, emitter, entry_points_faker
):
    entry_points_faker()

    app = Application(app_metadata, fake_services)
    app._setup_logging()
    app._load_plugins()
    emitter.assert_debug(f"Loading app plugin {PLUGIN_ENTRY_POINT_NAME}")


@pytest.mark.usefixtures("fake_project_file")
def test_app_two_plugins_loaded(
    app_metadata, fake_service, fake_services, emitter, entry_points_faker
):
    entry_points_faker(
        [
            (PLUGIN_ENTRY_POINT_NAME, PLUGIN_MODULE_NAME, configure),
            ("anothername", "anothermodule", configure),
        ]
    )

    app = Application(app_metadata, fake_services)
    app._setup_logging()
    app._load_plugins()
    emitter.assert_debug(f"Loading app plugin {PLUGIN_ENTRY_POINT_NAME}")
    emitter.assert_debug("Loading app plugin anothername")


@pytest.mark.usefixtures("fake_project_file")
def test_app_plugin_adds_service(
    app_metadata, fake_service, fake_services, emitter, entry_points_faker
):
    class FakeService(AppService):
        def get_a_thing(self):
            return "a thing"

    def configure(app: Application) -> None:
        services.ServiceFactory.register("fake", FakeService)

    entry_points_faker([(PLUGIN_ENTRY_POINT_NAME, PLUGIN_MODULE_NAME, configure)])
    app = Application(app_metadata, fake_services)
    app._setup_logging()
    app._load_plugins()

    assert cast(FakeService, app.services.get("fake")).get_a_thing() == "a thing"


@pytest.mark.usefixtures("fake_project_file")
def test_app_plugin_adds_commands(
    mocker,
    capsys,
    app_metadata,
    fake_service,
    fake_services,
    emitter,
    entry_points_faker,
):
    class FakeCommand(commands.AppCommand):
        name = "fake"
        help_msg = "Make <name> fake"
        overview = textwrap.dedent(
            """
            Fake an available <name> with something fake,
            making your organisation a faker."""
        )

        @override
        def fill_parser(self, parser: argparse.ArgumentParser) -> None:
            parser.add_argument(
                "name",
                type=str,
                help="Name of fake thing",
            )
            parser.add_argument(
                "--real",
                action="store_true",
                help="Register the fake thing as real",
            )

        @override
        def run(self, parsed_args: argparse.Namespace) -> None:
            emit.message(
                f"Faked faking {parsed_args.name} ({'NOT' if not parsed_args.real else ''} real)"
            )

    def configure(app: Application) -> None:
        app.add_command_group("Fake management", [FakeCommand])

    entry_points_faker([(PLUGIN_ENTRY_POINT_NAME, PLUGIN_MODULE_NAME, configure)])

    emit_mock = mocker.patch("craft_cli.emit")

    mocker.patch.object(sys, "argv", [FAKE_APP, "help"])
    app = Application(app_metadata, fake_services)
    with pytest.raises(SystemExit) as e:
        app.run()

    assert e.value.code == os.EX_OK
    emit_mock.ended_ok.assert_called_once_with()

    out, err = capsys.readouterr()
    assert not out

    # Make sure the command exists in the help output
    assert "Fake management:  fake" in err
