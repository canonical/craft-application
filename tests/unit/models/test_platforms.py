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
"""Unit tests for platform models."""

import pytest
from craft_application.models.platforms import PlatformsDict, ReservedPlatformName
from pydantic import TypeAdapter, ValidationError


@pytest.mark.parametrize("reserved_name", ReservedPlatformName)
def test_reserved_name(reserved_name: ReservedPlatformName):
    with pytest.raises(
        ValidationError, match=f"Platform name '{reserved_name.value}' is reserved."
    ):
        TypeAdapter(PlatformsDict).validate_python(
            {reserved_name.value: {"build-on": ["riscv64"], "build-for": ["riscv64"]}}
        )
