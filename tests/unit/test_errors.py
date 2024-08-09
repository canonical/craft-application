# This file is part of craft_application.
#
# Copyright 2023 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for error classes."""
import textwrap

import craft_parts
import pydantic
import pytest
import pytest_check
from craft_application.errors import CraftValidationError, PartsLifecycleError
from pydantic import BaseModel
from typing_extensions import Self


@pytest.mark.parametrize(
    "err",
    [
        craft_parts.PartsError("Yo"),
        craft_parts.PartsError(brief="yo", details="sup", resolution="IDK fix it"),
    ],
)
def test_parts_lifecycle_error_from_parts_error(err):
    actual = PartsLifecycleError.from_parts_error(err)

    pytest_check.equal(err.brief, actual.args[0])
    pytest_check.equal(err.details, actual.details)
    pytest_check.equal(err.resolution, actual.resolution)


@pytest.mark.parametrize(
    ("err", "expected"),
    [
        (OSError(0, "strerror"), PartsLifecycleError("strerror", details="OSError")),
        (
            OSError(1, "some error string", "/some/file"),
            PartsLifecycleError(
                "/some/file: some error string",
                details="PermissionError: filename: '/some/file'",
            ),
        ),
        (
            OSError(2, "not found", "/file", None, "/another"),
            PartsLifecycleError(
                "/file: not found",
                details="FileNotFoundError: filename: '/file', filename2: '/another'",
            ),
        ),
    ],
)
def test_parts_lifecycle_error_from_os_error(
    err: OSError, expected: PartsLifecycleError
):
    actual = PartsLifecycleError.from_os_error(err)

    assert actual == expected


class Model(BaseModel):
    gt_int: int = pydantic.Field(gt=42)
    a_float: float
    b_int: int = 0

    @pydantic.model_validator(mode="after")
    def b_smaller_gt(self) -> Self:
        if self.b_int >= self.gt_int:
            raise ValueError("'b_int' must be smaller than 'gt_int'")
        return self


def test_validation_error_from_pydantic():
    data = {"gt_int": 21, "a_float": "not a float"}
    try:
        Model(**data)
    except pydantic.ValidationError as e:
        err = CraftValidationError.from_pydantic(e, file_name="myfile.yaml")
    else:  # pragma: no cover
        pytest.fail("Model failed to fail to validate!")

    expected = textwrap.dedent(
        """
        Bad myfile.yaml content:
        - input should be greater than 42 (in field 'gt_int')
        - input should be a valid number, unable to parse string as a number (in field 'a_float')
        """
    ).strip()

    message = str(err)
    assert message == expected


def test_validation_error_from_pydantic_model():
    data = {"gt_int": 100, "a_float": 1.0, "b_int": 3000}
    try:
        Model(**data)
    except pydantic.ValidationError as e:
        err = CraftValidationError.from_pydantic(e, file_name="myfile.yaml")
    else:  # pragma: no cover
        pytest.fail("Model failed to fail to validate!")

    expected = textwrap.dedent(
        """
        Bad myfile.yaml content:
        - 'b_int' must be smaller than 'gt_int'
        """
    ).strip()

    message = str(err)
    assert message == expected
