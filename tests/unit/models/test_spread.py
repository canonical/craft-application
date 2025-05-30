# This file is part of craft-application.
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
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Unit tests for Spread models."""

import io
import pathlib

import pytest
from craft_application import util
from craft_application.models import spread as model


@pytest.mark.parametrize(
    ("systems", "expected"),
    [
        (["ubuntu-24.04-64"], ["ubuntu-24.04-64"]),
        (
            [{"ubuntu-24.04-64": None}],
            [{"ubuntu-24.04-64": model.SpreadSystem(workers=1)}],
        ),
        (
            ["ubuntu-24.04-64", {"ubuntu-24.04-64": None}],
            ["ubuntu-24.04-64", {"ubuntu-24.04-64": model.SpreadSystem(workers=1)}],
        ),
    ],
)
def test_systems_from_craft(systems, expected):
    assert model.SpreadBackend.systems_from_craft(systems) == expected


_CRAFT_SPREAD = """
project: project-name

backends:
  craft:
    type: craft
    systems:
      - ubuntu-24.04:

suites:
  spread/general/:
    summary: General integration tests
    environment:
      FOO: bar
    prepare: |
      snap install $CRAFT_ARTIFACT --dangerous
    restore: |
      snap remove my-snap --purge

exclude:
  - .git

kill-timeout: 1h
"""


def test_spread_yaml_from_craft_spread():
    backend = model.SpreadBackend(
        type="type",
        allocate="allocate",
        discard="discard",
        prepare="prepare",
        restore="restore",
        prepare_each="prepare_each",
        restore_each="restore each",
    )
    data = util.safe_yaml_load(io.StringIO(_CRAFT_SPREAD))
    craft_spread = model.CraftSpreadYaml.unmarshal(data)

    spread = model.SpreadYaml.from_craft(
        craft_spread,
        craft_backend=backend,
        artifact=pathlib.Path("artifact"),
        resources={"my-resource": pathlib.Path("resource")},
    )

    assert spread == model.SpreadYaml(
        project="craft-test",
        environment={
            "SUDO_USER": "",
            "SUDO_UID": "",
            "LANG": "C.UTF-8",
            "LANGUAGE": "en",
            "PROJECT_PATH": "/root/proj",
            "CRAFT_ARTIFACT": "$PROJECT_PATH/artifact",
            "CRAFT_RESOURCE_MY_RESOURCE": "$PROJECT_PATH/resource",
        },
        backends={
            "craft": model.SpreadBackend(
                type="type",
                allocate="allocate",
                discard="discard",
                systems=[{"ubuntu-24.04": model.SpreadSystem(workers=1)}],
                prepare="prepare",
                restore="restore",
                prepare_each="prepare_each",
                restore_each="restore each",
            )
        },
        suites={
            "spread/general/": model.SpreadSuite(
                summary="General integration tests",
                systems=[],
                environment={"FOO": "bar"},
                prepare="snap install $CRAFT_ARTIFACT --dangerous\n",
                restore="snap remove my-snap --purge\n",
                prepare_each=None,
                restore_each=None,
            )
        },
        exclude=[".git"],
        path="/root/proj",
        kill_timeout="1h",
        reroot="..",
        prepare=None,
        restore=None,
        prepare_each=None,
        restore_each=None,
    )


@pytest.mark.parametrize(
    ("name", "var"),
    [
        ("", ""),
        ("Foo-123", "FOO_123"),
        ("10.0/2=5.0", "10_0_2_5_0"),
    ],
)
def test_translate_resource_name(name, var):
    var_name = model.SpreadYaml._translate_resource_name(name)
    assert var_name == var
