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
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for internal model utilities."""
import pathlib

import pytest
from craft_application.util import yaml
from yaml.error import YAMLError

TEST_DIR = pathlib.Path(__file__).parent


@pytest.mark.parametrize("file", (TEST_DIR / "valid_yaml").glob("*.yaml"))
def test_safe_yaml_loader_valid(file):
    with file.open() as f:
        yaml.safe_yaml_load(f)


@pytest.mark.parametrize("file", (TEST_DIR / "invalid_yaml").glob("*.yaml-invalid"))
def test_safe_yaml_loader_invalid(file):
    with pytest.raises(YAMLError):
        with file.open() as f:
            yaml.safe_yaml_load(f)
