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

import pytest
from craft_application.services import provider
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


@pytest.fixture()
def provider_service(app_metadata, fake_project, fake_build_plan, fake_services):
    """Provider service with install snap disabled for integration tests"""
    return provider.ProviderService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=pathlib.Path(),
        build_plan=fake_build_plan,
        install_snap=False,
    )


@pytest.fixture()
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
