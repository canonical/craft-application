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
"""Unit tests for the FetchService.

Note that most of the fetch-service functionality is already tested either on:
- unit/test_fetch.py, for unit tests of the endpoint calls, or;
- integration/services/test_fetch.py, for full integration tests.

As such, this module mostly unit-tests error paths coming from wrong usage of
the FetchService class.
"""
import re
from unittest.mock import MagicMock

import pytest
from craft_application import fetch, services


@pytest.fixture()
def fetch_service(app, fake_services):
    return services.FetchService(app, fake_services)


def test_create_session_already_exists(fetch_service):
    fetch_service._session_data = fetch.SessionData(id="id", token="token")

    expected = re.escape(
        "create_session() called but there's already a live fetch-service session."
    )
    with pytest.raises(ValueError, match=expected):
        fetch_service.create_session(instance=MagicMock())


def test_teardown_session_no_session(fetch_service):
    expected = re.escape(
        "teardown_session() called with no live fetch-service session."
    )

    with pytest.raises(ValueError, match=expected):
        fetch_service.teardown_session()
