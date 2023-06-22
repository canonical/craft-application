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
import craft_parts
import pytest
import pytest_check
from craft_application.errors import PartsLifecycleError


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
