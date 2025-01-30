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

from craft_application import Application

FAKE_APP = "boopcraft"
PLUGIN_GROUP_NAME = "craft-application-plugins.application"
PLUGIN_ENTRY_POINT_NAME = f"{FAKE_APP}_plugin"
PLUGIN_MODULE_NAME = f"{FAKE_APP}_module"


class FakeCraftApplicationPlugin:
    def __init__(self):
        ...

    def wef(self):
        print("WEF!")


class FakeDistribution(Distribution):
    def read_text(self, filename):
        if filename == "entry_points.txt":
            return f"""
[{PLUGIN_GROUP_NAME}]
{PLUGIN_ENTRY_POINT_NAME} = {PLUGIN_MODULE_NAME}
"""
        if filename == "METADATA":
            return """Name: wef"""
        return ""

    def locate_file(self, path):
        raise NotImplementedError


class FakeDistributionFinder(DistributionFinder):
    def find_distributions(self, context=None):
        return [FakeDistribution()]


@pytest.mark.usefixtures("fake_project_file")
def test_app_plugin(monkeypatch, app_metadata, fake_services):
    # Set up the fakery
    sys.meta_path.append(FakeDistributionFinder)
    sys.modules[PLUGIN_MODULE_NAME] = FakeCraftApplicationPlugin()

    app = Application(app_metadata, fake_services)
    print(app)
    raise AssertionError
