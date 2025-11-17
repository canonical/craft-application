# This file is part of craft-application.
#
# Copyright 2023-2025 Canonical Ltd.
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
"""Unit tests for platform models."""

import re

import pydantic
import pytest
from craft_application.models.platforms import (
    RESERVED_PLATFORM_NAMES,
    PlatformsDict,
)
from hypothesis import given, strategies


@pytest.mark.parametrize("name", RESERVED_PLATFORM_NAMES)
def test_platform_name_reserved(name):
    adapter = pydantic.TypeAdapter(PlatformsDict)
    with pytest.raises(
        ValueError, match=re.escape(f"Reserved platform name: {name!r}")
    ):
        adapter.validate_python(
            {name: {"build-on": ["riscv64"], "build-for": ["s390x"]}}
        )


@pytest.mark.parametrize("name", ["/"])
def test_platform_name_invalid_character(name):
    adapter = pydantic.TypeAdapter(PlatformsDict)
    with pytest.raises(
        ValueError, match="Platform names cannot contain the '.' character"
    ):
        adapter.validate_python(
            {name: {"build-on": ["riscv64"], "build-for": ["s390x"]}}
        )


@given(
    strategies.text(min_size=1).filter(
        lambda s: s not in RESERVED_PLATFORM_NAMES and "/" not in s
    ),
)
def test_fuzz_platform_name(name):
    adapter = pydantic.TypeAdapter(PlatformsDict)
    adapter.validate_python({name: {"build-on": ["riscv64"], "build-for": ["s390x"]}})
