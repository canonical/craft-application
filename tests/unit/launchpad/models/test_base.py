#  This file is part of craft-application.
#
#  Copyright 2024 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Basic Launchpad object tests."""

import enum
from typing import Any
from unittest import mock

import pytest
from craft_application.launchpad import Launchpad, LaunchpadObject
from lazr.restfulclient.resource import Entry
from typing_extensions import Self


class Type(enum.Enum):
    """Resource types for testing."""

    THIS = "this"
    VALID = "valid_type"
    NAME = "something"


class FakeLaunchpadObject(LaunchpadObject):
    """A Launchpad object for testing."""

    _resource_types = Type
    _attr_map = {}

    @classmethod
    def get(cls, *args: Any, **kwargs: Any) -> Self:
        raise NotImplementedError

    @classmethod
    def new(cls, *args: Any, **kwargs: Any) -> Self:
        raise NotImplementedError


@pytest.mark.parametrize("resource_type", [t.value for t in Type])
def test_init_success(resource_type):
    mock_entry = mock.Mock(spec=Entry, resource_type=resource_type)
    mock_entry.resource_type_link = f"https://localhost/#{resource_type}"
    mock_entry.lp_attributes = []
    mock_lp = mock.Mock(spec_set=Launchpad)

    FakeLaunchpadObject(mock_lp, mock_entry)


@pytest.mark.parametrize("resource_type", ["ThIs", "invalid_type", "NAME"])
def test_invalid_resource_type(resource_type):
    mock_entry = mock.Mock(spec=Entry, resource_type=resource_type)
    mock_entry.resource_type_link = f"https://localhost/#{resource_type}"
    mock_entry.lp_attributes = []
    mock_lp = mock.Mock(spec_set=Launchpad)

    with pytest.raises(
        TypeError,
        match="Launchpadlib entry not a valid resource type for",
    ):
        FakeLaunchpadObject(mock_lp, mock_entry)
