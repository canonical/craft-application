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
import pytest_check
from craft_application import errors
from craft_application.util import yaml

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
        with pytest.raises(
            errors.YamlError, match=f"error parsing {file.name!r}: "
        ) as exc_info:
            yaml.safe_yaml_load(f)

    pytest_check.is_in(file.name, exc_info.value.resolution)
    pytest_check.is_true(str(exc_info.value.resolution).endswith("contains valid YAML"))
    pytest_check.is_in("found", exc_info.value.details)


@pytest.mark.parametrize(
    ("yaml_text", "error_msg"),
    [
        (
            "thing: \nthing:\n",
            "error parsing 'testcraft.yaml': found duplicate key 'thing'",
        ),
        (
            "{{unhashable}}:",
            "error parsing 'testcraft.yaml': found unhashable key",
        ),
    ],
)
def test_safe_yaml_loader_specific_error(yaml_text: str, error_msg: str):
    f = io.StringIO(yaml_text)
    f.name = "testcraft.yaml"

    with pytest.raises(errors.YamlError) as exc_info:
        yaml.safe_yaml_load(f)

    assert exc_info.value.args[0] == error_msg


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
        (
            {"ordered": "no", "comes_first": False, "long_key": "123\n456\n789"},
            {},
            "ordered: 'no'\ncomes_first: false\nlong_key: |-\n  123\n  456\n  789\n",
        ),
        (
            {"ordered": "no", "comes_first": False, "unicode": "👍"},
            {},
            "ordered: 'no'\ncomes_first: false\nunicode: 👍\n",
        ),
    ],
)
def test_dump_yaml_to_stream(data, kwargs, expected):
    with io.StringIO() as file:
        yaml.dump_yaml(data, file, **kwargs)

        assert file.getvalue() == expected
