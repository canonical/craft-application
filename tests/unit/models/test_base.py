# This file is part of craft-application.
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
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for CraftBaseModel"""
from pathlib import Path

import pydantic
import pytest
from craft_application import errors, models
from hypothesis import given, strategies
from overrides import override


class MyBaseModel(models.CraftBaseModel):

    value1: int
    value2: str

    @pydantic.field_validator("value1", mode="after")
    @classmethod
    def _validate_value1(cls, _v):
        raise ValueError("Bad value1 value")

    @pydantic.field_validator("value2", mode="after")
    @classmethod
    def _validate_value2(cls, _v):
        raise ValueError("Bad value2 value")

    @classmethod
    @override
    def model_reference_slug(cls) -> str | None:
        return "/mymodel.html"


def test_model_reference_slug_errors():
    data = {
        "value1": 1,
        "value2": "hi",
    }
    with pytest.raises(errors.CraftValidationError) as err:
        MyBaseModel.from_yaml_data(data, Path("testcraft.yaml"))

    expected = (
        "Bad testcraft.yaml content:\n"
        "- bad value1 value (in field 'value1')\n"
        "- bad value2 value (in field 'value2')"
    )
    assert str(err.value) == expected
    assert err.value.doc_slug == "/mymodel.html"


class CoerceModel(models.CraftBaseModel):

    stringy: str


@given(
    strategies.one_of(
        strategies.integers(),
        strategies.floats(),
        strategies.decimals(),
        strategies.text(),
    )
)
def test_model_coerces_to_strings(value):
    result = CoerceModel.model_validate({"stringy": value})

    assert result.stringy == str(value)
