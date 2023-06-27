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
from craft_application import services


@pytest.fixture()
def provider_service(app_metadata, fake_project):
    return services.ProviderService(app_metadata, fake_project)


@pytest.fixture()
def mock_services(app_metadata, fake_project, fake_package_service_class):
    factory = services.ServiceFactory(
        app_metadata, fake_project, PackageClass=fake_package_service_class
    )
    factory._services["lifecycle"] = mock.Mock(spec=services.LifecycleService)
    factory._services["package"] = mock.Mock(spec=services.PackageService)
    factory._services["provider"] = mock.Mock(spec=services.ProviderService)
    return factory
