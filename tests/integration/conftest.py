#  This file is part of craft-application.
#
#  Copyright 2023 Canonical Ltd.
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
"""Configuration for craft-application integration tests."""

import os
import pathlib
import sys
import tempfile
from unittest import mock

import craft_platforms
import pytest
from craft_application import launchpad
from craft_application.services import provider, remotebuild
from craft_providers import lxd, multipass


def pytest_configure(config: pytest.Config):
    config.addinivalue_line("markers", "multipass: tests that require multipass")
    config.addinivalue_line("markers", "lxd: tests that require lxd")


def pytest_runtest_setup(item: pytest.Item):
    if sys.platform != "linux":
        if any(item.iter_markers("lxd")):
            pytest.skip("lxd tests only run on Linux")
    elif not lxd.is_installed() and any(item.iter_markers("lxd")):
        pytest.skip("lxd not installed")

    if not multipass.is_installed() and any(item.iter_markers("multipass")):
        pytest.skip("multipass not installed")


@pytest.fixture
def provider_service(app_metadata, fake_services):
    """Provider service with install snap disabled for integration tests"""
    return provider.ProviderService(
        app_metadata,
        fake_services,
        work_dir=pathlib.Path(),
        install_snap=False,
    )


@pytest.fixture(scope="session")
def anonymous_remote_build_service(default_app_metadata):
    """Provider service with install snap disabled for integration tests"""
    service = remotebuild.RemoteBuildService(default_app_metadata, services=mock.Mock())
    service.lp = launchpad.Launchpad.anonymous("testcraft")
    return service


@pytest.fixture
def snap_safe_tmp_path():
    """A temporary path accessible to snap-confined craft providers.

    Some providers (notably Multipass) don't have access to /tmp  on Linux. This
    provides a temporary path that the provider can use, preferring $XDG_RUNTIME_DIR
    if it exists.

    On Non-Linux platforms providers aren't confined, so we can use the default
    temporary directory.
    """
    if sys.platform != "linux":
        with tempfile.TemporaryDirectory() as temp_dir:
            yield pathlib.Path(temp_dir)
        return
    directory = os.getenv("XDG_RUNTIME_DIR")
    with tempfile.TemporaryDirectory(
        prefix="craft-application-test-",
        suffix=".tmp",
        dir=directory or pathlib.Path.home(),
    ) as temp_dir:
        yield pathlib.Path(temp_dir)


@pytest.fixture
def pretend_jammy(mocker) -> None:
    """Pretend we're running on jammy. Used for tests that use destructive mode."""
    fake_host = craft_platforms.DistroBase("ubuntu", "22.04")
    mocker.patch(
        "craft_platforms.DistroBase.from_linux_distribution", return_value=fake_host
    )


@pytest.fixture
def hello_repository_lp_url() -> str:
    return "https://git.launchpad.net/ubuntu/+source/hello"
