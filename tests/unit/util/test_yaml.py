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
import re

import craft_platforms
import pytest
from craft_application import errors
from craft_application.util import yaml
from craft_cli.pytest_plugin import raises_craft_error

TEST_DIR = pathlib.Path(__file__).parent


@pytest.mark.parametrize("file", tuple((TEST_DIR / "valid_yaml").glob("*.yaml")))
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
        with raises_craft_error(
            errors.YamlError,
            match=f"error parsing {re.escape(repr(file.name))}: ",
            resolution=f"{re.escape(file.name)} contains valid YAML$",
            details="found",
        ):
            yaml.safe_yaml_load(f)


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

    with raises_craft_error(errors.YamlError, match=f"^{re.escape(error_msg)}$"):
        yaml.safe_yaml_load(f)


def test_safe_yaml_loader_non_utf8(tmp_path):
    """A non-UTF-8 file surfaces a friendly YamlError, not an uncaught UnicodeDecodeError."""
    bad_file = tmp_path / "testcraft.yaml"
    bad_file.write_bytes("name: test\n".encode("utf-32"))

    with bad_file.open() as f:  # default UTF-8 text mode
        with raises_craft_error(
            errors.YamlError,
            match=f"{re.escape(bad_file.name)}.*is not valid UTF-8",
            resolution="encoded in UTF-8$",
        ):
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
        ({"arch": craft_platforms.DebianArchitecture.RISCV64}, {}, "arch: riscv64\n"),
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
