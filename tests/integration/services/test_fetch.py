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
"""Tests for FetchService."""
import shutil
import socket

import pytest
from craft_application import errors, fetch, services


@pytest.fixture(autouse=True)
def _set_test_base_dir(mocker):
    original = fetch._get_service_base_dir()
    test_dir = original / "test"
    test_dir.mkdir(exist_ok=False)
    mocker.patch.object(fetch, "_get_service_base_dir", return_value=test_dir)
    yield
    shutil.rmtree(test_dir)


@pytest.fixture()
def app_service(app_metadata, fake_services):
    fetch_service = services.FetchService(app_metadata, fake_services)
    yield fetch_service
    fetch_service.shutdown(force=True)


def test_start_service(app_service):
    assert not fetch.is_service_online()
    app_service.setup()
    assert fetch.is_service_online()


def test_start_service_already_up(app_service, request):
    # Create a fetch-service "manually"
    fetch_process = fetch.start_service()
    assert fetch.is_service_online()
    # Ensure its cleaned up when the test is done
    if fetch_process is not None:
        request.addfinalizer(lambda: fetch.stop_service(fetch_process))

    app_service.setup()
    assert fetch.is_service_online()


@pytest.mark.parametrize(
    "port", [fetch._DEFAULT_CONFIG.control, fetch._DEFAULT_CONFIG.proxy]
)
def test_start_service_port_taken(app_service, request, port):
    # "Occupy" one of the necessary ports manually.
    soc = socket.create_server(("localhost", port), reuse_port=True)
    request.addfinalizer(soc.close)

    assert not fetch.is_service_online()

    proxy = fetch._DEFAULT_CONFIG.proxy
    control = fetch._DEFAULT_CONFIG.control

    expected = f"fetch-service ports {proxy} and {control} are already in use."
    with pytest.raises(errors.FetchServiceError, match=expected):
        app_service.setup()


def test_shutdown_service(app_service):
    assert not fetch.is_service_online()

    app_service.setup()
    assert fetch.is_service_online()

    # By default, shutdown() without parameters doesn't actually stop the
    # fetch-service.
    app_service.shutdown()
    assert fetch.is_service_online()

    # shutdown(force=True) must stop the fetch-service.
    app_service.shutdown(force=True)
    assert not fetch.is_service_online()
