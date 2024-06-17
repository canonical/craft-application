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
import contextlib
import shutil
import socket
from unittest import mock

import craft_providers
import pytest
from craft_application import errors, fetch, services, util
from craft_application.models import BuildInfo
from craft_providers import bases


@pytest.fixture(autouse=True)
def _set_test_base_dir(mocker):
    original = fetch._get_service_base_dir()
    test_dir = original / "test"
    test_dir.mkdir(exist_ok=True)
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


def test_create_teardown_session(app_service, mocker):
    mocker.patch.object(fetch, "_get_gateway", return_value="127.0.0.1")
    app_service.setup()

    assert len(fetch.get_service_status()["active-sessions"]) == 0

    app_service.create_session(
        instance=mock.MagicMock(spec_set=craft_providers.Executor)
    )
    assert len(fetch.get_service_status()["active-sessions"]) == 1

    report = app_service.teardown_session()
    assert len(fetch.get_service_status()["active-sessions"]) == 0

    assert "artefacts" in report


@pytest.fixture()
def lxd_instance(snap_safe_tmp_path, provider_service):
    provider_service.get_provider("lxd")

    arch = util.get_host_architecture()
    build_info = BuildInfo("foo", arch, arch, bases.BaseName("ubuntu", "22.04"))
    instance = provider_service.instance(build_info, work_dir=snap_safe_tmp_path)

    with instance as executor:
        yield executor

    if executor is not None:
        with contextlib.suppress(craft_providers.ProviderError):
            executor.delete()


def test_build_instance_integration(app_service, lxd_instance):

    app_service.setup()

    env = app_service.create_session(lxd_instance)
    try:
        lxd_instance.execute_run(
            ["apt", "install", "-y", "hello"], check=True, env=env, capture_output=True
        )
    finally:
        report = app_service.teardown_session()

    # Check that the installation of the "hello" deb went through the inspector.
    debs = set()
    deb_type = "application/vnd.debian.binary-package"

    for artefact in report["artefacts"]:
        metadata_name = artefact["metadata"]["name"]
        metadata_type = artefact["metadata"]["type"]
        if metadata_name == "hello" and metadata_type == deb_type:
            debs.add(metadata_name)

    assert "hello" in debs
