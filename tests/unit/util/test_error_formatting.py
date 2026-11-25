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
"""Tests for error formatting."""

import textwrap
from typing import TYPE_CHECKING

import pytest
import pytest_check
from craft_application.util.error_formatting import (
    MAX_INPUT_LENGTH,
    FieldLocationTuple,
    format_pydantic_error,
    format_pydantic_error_details,
    format_pydantic_errors,
)

if TYPE_CHECKING:  # pragma: no-cover
    from pydantic_core import ErrorDetails


@pytest.mark.parametrize(
    ("loc_str", "location", "field"),
    [
        ("abc", "top-level", "abc"),
        ("abc.def", "abc", "def"),
        ("abc.def.ghi", "abc.def", "ghi"),
    ],
)
def test_field_location_tuple_from_str(loc_str, location, field):
    actual = FieldLocationTuple.from_str(loc_str)

    pytest_check.equal(actual.location, location)
    pytest_check.equal(actual.field, field)
    pytest_check.equal(actual, FieldLocationTuple(field, location))


@pytest.mark.parametrize(
    ("field_path", "value", "message", "expected"),
    [
        (
            ["foo"],
            None,
            "field required",
            "- field 'foo' required in top-level configuration",
        ),
        (
            ["foo", 0, "bar"],
            None,
            "field required",
            "- field 'bar' required in 'foo[0]' configuration",
        ),
        (
            ["foo"],
            "I don't belong here!",
            "extra fields not permitted",
            "- extra field 'foo' not permitted in top-level configuration",
        ),
        (
            ["foo", 2, "bar"],
            "I don't belong here!",
            "extra fields not permitted",
            "- extra field 'bar' not permitted in 'foo[2]' configuration",
        ),
        (
            ["foo"],
            "I don't belong here!",
            "the list has duplicated items",
            "- duplicate 'foo' entry not permitted in top-level configuration",
        ),
        (
            ["foo", 1, "bar"],
            "bar",
            "the list has duplicated items",
            "- duplicate 'bar' entry not permitted in 'foo[1]' configuration",
        ),
        (["__root__"], None, "generic error message", "- generic error message"),
        (
            ["foo", 2, "bar", 1, "baz"],
            ["this", "is", "a", "list", "of", "strings"],
            "error!",
            "- error! (in field 'foo[2].bar[1].baz', input: ['this', 'is', 'a', 'list', 'of', 'strings'])",
        ),
    ],
)
def test_format_pydantic_error(field_path, value, message, expected):
    actual = format_pydantic_error(
        {
            "loc": field_path,
            "msg": message,
            "type": "misc-error",
            "input": value,
        },
    )

    assert actual == expected


def test_format_pydantic_error_omits_long_input():
    project = {"name": "my-snap", "base": "core26", "description": "x" * 300}

    actual = format_pydantic_error(
        {
            "loc": ("has-base", "core26"),
            "msg": "required field 'version' is not set and 'adopt-info' not used.",
            "type": "value_error",
            "input": project,
        },
    )

    assert actual == (
        "- required field 'version' is not set and 'adopt-info' not used. "
        "(in field 'has-base.core26')"
    )


def test_format_pydantic_error_keeps_input_at_limit():
    value = "x" * (MAX_INPUT_LENGTH - 2)

    actual = format_pydantic_error(
        {"loc": ("foo",), "msg": "bad", "type": "misc-error", "input": value},
    )

    assert actual == f"- bad (in field 'foo', input: {value!r})"


def test_format_pydantic_error_details_long_input():
    project = {"name": "my-snap", "base": "core26", "description": "x" * 300}
    errors = [
        {"loc": ("has-base", "core26"), "msg": "bad", "type": "x", "input": project},
        {"loc": ("foo",), "msg": "bad", "type": "x", "input": 1},
    ]

    actual = format_pydantic_error_details(errors)

    assert actual == f"- input for field 'has-base.core26': {project!r}"


def test_format_pydantic_error_details_short_input():
    errors = [{"loc": ("foo",), "msg": "bad", "type": "x", "input": "x" * 100}]

    assert format_pydantic_error_details(errors) is None


@pytest.mark.parametrize(
    ("errors", "file_name", "expected"),
    [
        (
            [{"loc": ["__root__"], "msg": "something's wrong", "input": None}],
            "this.yaml",
            "Bad this.yaml content:\n- something's wrong",
        )
    ],
)
def test_format_pydantic_errors(errors, file_name, expected):
    actual = format_pydantic_errors(errors, file_name=file_name)

    assert actual == expected


def test_format_pydantic_error_normalization():
    errors: list[ErrorDetails] = [
        {
            "loc": ("a", "b", "c"),
            "msg": "Can't do it",
            "input": "AAAAAAAAAHHHHHH!",
            "type": "unused",
        },
        {
            "loc": ("d", "e", "f"),
            "msg": "something's wrong",
            "input": "😱",
            "type": "unused",
        },
        {
            "loc": ("x",),
            "msg": "Something's not right",
            "input": "🙀🙀🙀",
            "type": "unused",
        },
    ]

    result = format_pydantic_errors(
        errors,
        file_name="this.yaml",
    )
    expected = textwrap.dedent(
        """
        Bad this.yaml content:
        - can't do it (in field 'a.b.c', input: 'AAAAAAAAAHHHHHH!')
        - something's wrong (in field 'd.e.f', input: '😱')
        - something's not right (in field 'x', input: '🙀🙀🙀')
    """
    ).strip()
    assert result == expected
