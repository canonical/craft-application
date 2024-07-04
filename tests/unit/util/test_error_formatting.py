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

import pytest
import pytest_check
from craft_application.util.error_formatting import (
    FieldLocationTuple,
    format_pydantic_error,
    format_pydantic_errors,
)


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
    ("field_path", "message", "expected"),
    [
        (
            ["foo"],
            "field required",
            "- field 'foo' required in top-level configuration",
        ),
        (
            ["foo", 0, "bar"],
            "field required",
            "- field 'bar' required in 'foo[0]' configuration",
        ),
        (
            ["foo"],
            "extra fields not permitted",
            "- extra field 'foo' not permitted in top-level configuration",
        ),
        (
            ["foo", 2, "bar"],
            "extra fields not permitted",
            "- extra field 'bar' not permitted in 'foo[2]' configuration",
        ),
        (
            ["foo"],
            "the list has duplicated items",
            "- duplicate 'foo' entry not permitted in top-level configuration",
        ),
        (
            ["foo", 1, "bar"],
            "the list has duplicated items",
            "- duplicate 'bar' entry not permitted in 'foo[1]' configuration",
        ),
        (["__root__"], "generic error message", "- generic error message"),
        (
            ["foo", 2, "bar", 1, "baz"],
            "error!",
            "- error! (in field 'foo[2].bar[1].baz')",
        ),
    ],
)
def test_format_pydantic_error(field_path, message, expected):
    actual = format_pydantic_error(field_path, message)

    assert actual == expected


@pytest.mark.parametrize(
    ("errors", "file_name", "expected"),
    [
        (
            [{"loc": ["__root__"], "msg": "something's wrong"}],
            "this.yaml",
            "Bad this.yaml content:\n- something's wrong",
        )
    ],
)
def test_format_pydantic_errors(errors, file_name, expected):
    actual = format_pydantic_errors(errors, file_name=file_name)

    assert actual == expected


def test_format_pydantic_error_normalization():
    errors = [
        {"loc": ["a.b.c"], "msg": "Can't do it"},
        {"loc": ["d.e.f"], "msg": "something's wrong"},
        {"loc": ["x"], "msg": "Something's not right"},
    ]

    result = format_pydantic_errors(
        errors, file_name="this.yaml"  # pyright: ignore[reportArgumentType]
    )
    expected = textwrap.dedent(
        """
        Bad this.yaml content:
        - can't do it (in field 'a.b.c')
        - something's wrong (in field 'd.e.f')
        - something's not right (in field 'x')
    """
    ).strip()
    assert result == expected
