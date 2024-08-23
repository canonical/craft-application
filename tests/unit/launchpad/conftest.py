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

from unittest import mock

import lazr.restfulclient.resource
import pytest
from craft_application.launchpad import Launchpad


@pytest.fixture
def mock_lplib():
    return mock.Mock(**{"me.name": "test_user"})


@pytest.fixture
def mock_lplib_entry():
    return mock.MagicMock(
        __class__=lazr.restfulclient.resource.Entry,
        resource_type_link="http://blah#this",
    )


@pytest.fixture
def fake_launchpad(mock_lplib):
    return Launchpad("testcraft", mock_lplib)
