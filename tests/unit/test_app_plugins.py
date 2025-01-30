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

import sys
from importlib.metadata import Distribution, DistributionFinder

import pytest

from craft_application import Application, AppService, services

FAKE_APP = "boopcraft"
PLUGIN_GROUP_NAME = "craft_application_plugins.application"
PLUGIN_ENTRY_POINT_NAME = f"{FAKE_APP}_plugin"
PLUGIN_MODULE_NAME = f"{FAKE_APP}_module"


class FakeCraftApplicationPlugin:
    def configure(self, application: Application) -> None:
        print("CALLED BACK YO")
        print(application.services.fake)


@pytest.fixture
def entry_points_faker():
    # Save unmodified sys.modules
    og_modules = sys.modules

    def entry_points_faker(entry_points: list[tuple[str, str, object]] | None = None):
        # All go under this group for our purposes
        entry_points_txt = f"[{PLUGIN_GROUP_NAME}]\n"

        if not entry_points:
            # Simple case
            entry_points = [
                (
                    PLUGIN_ENTRY_POINT_NAME,
                    PLUGIN_MODULE_NAME,
                    FakeCraftApplicationPlugin,
                )
            ]

        for entry_point_name, module_name, module_callable in entry_points:
            entry_points_txt += f"{entry_point_name} = {module_name}\n"
            sys.modules[module_name] = module_callable()

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
        sys.meta_path.append(FakeDistributionFinder)

    yield entry_points_faker

    # Restore environment
    sys.modules = og_modules
    sys.meta_path.pop()


@pytest.fixture
def fake_service():
    class FakeService(AppService): ...

    services.ServiceFactory.register("fake", FakeService)


def test_app_no_plugins(monkeypatch, app_metadata, fake_services, emitter):
    Application(app_metadata, fake_services)
    with pytest.raises(AssertionError):
        emitter.assert_progress("Loading app plugin .*", regex=True)


@pytest.mark.usefixtures("fake_project_file")
def test_app_plugin_loaded(
    app_metadata, fake_service, fake_services, emitter, entry_points_faker
):
    entry_points_faker()

    Application(app_metadata, fake_services)
    emitter.assert_progress(f"Loading app plugin {PLUGIN_ENTRY_POINT_NAME}")


@pytest.mark.usefixtures("fake_project_file")
def test_app_two_plugins_loaded(
    app_metadata, fake_service, fake_services, emitter, entry_points_faker
):
    entry_points_faker(
        [
            (PLUGIN_ENTRY_POINT_NAME, PLUGIN_MODULE_NAME, FakeCraftApplicationPlugin),
            ("anothername", "anothermodule", FakeCraftApplicationPlugin),
        ]
    )

    Application(app_metadata, fake_services)
    emitter.assert_progress(f"Loading app plugin {PLUGIN_ENTRY_POINT_NAME}")
    emitter.assert_progress("Loading app plugin anothername")
