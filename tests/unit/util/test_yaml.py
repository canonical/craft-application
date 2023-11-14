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
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for internal model utilities."""
import io
import pathlib

import pytest
from craft_application.util import yaml
from yaml.error import YAMLError

TEST_DIR = pathlib.Path(__file__).parent


@pytest.mark.parametrize("file", (TEST_DIR / "valid_yaml").glob("*.yaml"))
def test_safe_yaml_loader_valid(file):
    with file.open() as f:
        yaml.safe_yaml_load(f)


@pytest.mark.parametrize(
    "file",
    [
        pytest.param(file, id=file.name)
        for file in (TEST_DIR / "invalid_yaml").glob("*.yaml-invalid")
    ],
)
def test_safe_yaml_loader_invalid(file):
    with file.open() as f:
        with pytest.raises(YAMLError):
            yaml.safe_yaml_load(f)


@pytest.mark.parametrize(
    ("data", "kwargs", "expected"),
    [
        (None, {}, "null\n...\n"),
        ({"thing": "stuff!"}, {}, "thing: stuff!\n"),
        (
            {"ordered": "no", "comes_first": False},
            {},
            "ordered: 'no'\ncomes_first: false\n",
        ),
        (
            {"ordered": "yes", "comes_first": True},
            {"sort_keys": True},
            "comes_first: true\nordered: 'yes'\n",
        ),
    ],
)
def test_dump_yaml_to_string(data, kwargs, expected):
    actual = yaml.dump_yaml(data, **kwargs)

    assert actual == expected


@pytest.mark.parametrize(
    ("data", "kwargs", "expected"),
    [
        (None, {}, "null\n...\n"),
        ({"thing": "stuff!"}, {}, "thing: stuff!\n"),
        (
            {"ordered": "no", "comes_first": False},
            {},
            "ordered: 'no'\ncomes_first: false\n",
        ),
        (
            {"ordered": "yes", "comes_first": True},
            {"sort_keys": True},
            "comes_first: true\nordered: 'yes'\n",
        ),
    ],
)
def test_dump_yaml_to_stream(data, kwargs, expected):
    with io.StringIO() as file:
        yaml.dump_yaml(data, file, **kwargs)

        assert file.getvalue() == expected
