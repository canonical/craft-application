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
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Simple tests for the pytest plugin."""

import os
import pathlib
import platform
from unittest import mock

import craft_parts
import craft_platforms
import pytest
import pytest_check
from craft_application import services, util
from pyfakefs.fake_filesystem import FakeFilesystem


def test_sets_debug_mode_auto_used(app_metadata):
    assert os.getenv("CRAFT_DEBUG") == "1"

    config_service = services.ConfigService(app=app_metadata, services=mock.Mock())
    config_service.setup()
    assert config_service.get("debug") is True


@pytest.mark.usefixtures("production_mode")
def test_production_mode_sets_production_mode(app_metadata):
    assert os.getenv("CRAFT_DEBUG") == "0"

    config_service = services.ConfigService(app=app_metadata, services=mock.Mock())
    config_service.setup()
    assert config_service.get("debug") is False


@pytest.mark.usefixtures("managed_mode")
def test_managed_mode():
    assert services.ProviderService.is_managed() is True


@pytest.mark.usefixtures("destructive_mode")
def test_destructive_mode():
    assert services.ProviderService.is_managed() is False
    assert os.getenv("CRAFT_BUILD_ENVIRONMENT") == "host"


@pytest.mark.xfail(
    reason="Setup of this test should fail because the two fixtures cannot be used together.",
    raises=LookupError,
    strict=True,
)
@pytest.mark.usefixtures("managed_mode", "destructive_mode")
def test_managed_and_destructive_mode_mutually_exclusive():
    pass


def test_host_architecture(fake_host_architecture: craft_platforms.DebianArchitecture):
    platform_arch = fake_host_architecture.to_platform_arch()
    pytest_check.equal(platform_arch, platform.uname().machine)
    pytest_check.equal(platform_arch, platform.machine())
    pytest_check.equal(fake_host_architecture.value, util.get_host_architecture())
    pytest_check.equal(
        fake_host_architecture, craft_platforms.DebianArchitecture.from_host()
    )
    pytest_check.equal(
        fake_host_architecture.value, craft_parts.infos._get_host_architecture()
    )


def test_project_path_created(project_path, tmp_path):
    assert project_path.is_dir()
    # Check that it's not the hardcoded fake path for pyfakefs.
    assert project_path != pathlib.Path("/test/project")
    assert project_path == tmp_path / "project"


def test_project_path_created_with_pyfakefs(fs: FakeFilesystem, project_path):
    assert fs.exists(project_path)
    assert project_path.is_dir()
    # Check that it's the hardcoded fake path for pyfakefs.
    assert project_path == pathlib.Path("/test/project")


def test_in_project_path(in_project_path):
    assert pathlib.Path.cwd() == in_project_path
