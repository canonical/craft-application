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
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Configuration for craft-application unit tests."""
from __future__ import annotations

from unittest import mock

import pytest
from craft_application import services, util


@pytest.fixture(params=["amd64", "arm64", "riscv64"])
def fake_host_architecture(monkeypatch, request) -> str:
    monkeypatch.setattr(util, "get_host_architecture", lambda: request.param)
    return request.param


@pytest.fixture
def provider_service(
    app_metadata, fake_project, fake_build_plan, fake_services, tmp_path
):
    return services.ProviderService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=tmp_path,
        build_plan=fake_build_plan,
    )


@pytest.fixture
def mock_services(app_metadata, fake_project, fake_package_service_class):
    factory = services.ServiceFactory(
        app_metadata, project=fake_project, PackageClass=fake_package_service_class
    )
    factory.lifecycle = mock.Mock(spec=services.LifecycleService)
    factory.package = mock.Mock(spec=services.PackageService)
    factory.provider = mock.Mock(spec=services.ProviderService)
    factory.remote_build = mock.Mock(spec_set=services.RemoteBuildService)
    factory.fetch = mock.Mock(spec=services.FetchService)
    factory.init = mock.Mock(spec=services.InitService)
    return factory
