# This file is part of craft-application.
#
# Copyright 2024 Canonical Ltd.
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

"""Tests for platform utilities."""

import pytest
from craft_application import util
from craft_application.util.platforms import _ARCH_TRANSLATIONS_DEB_TO_PLATFORM


@pytest.mark.parametrize("arch", _ARCH_TRANSLATIONS_DEB_TO_PLATFORM.keys())
def test_is_valid_architecture_true(arch):
    assert util.is_valid_architecture(arch)


def test_is_valid_architecture_false():
    assert not util.is_valid_architecture("unknown")
