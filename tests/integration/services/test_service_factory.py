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
"""Integration tests for ServiceFactory."""
import pytest
from craft_application import services


def test_gets_real_services(
    check,
    app_metadata,
    fake_project,
    fake_package_service_class,
    fake_lifecycle_service_class,
    fake_provider_service_class,
):
    factory = services.ServiceFactory(
        app_metadata,
        project=fake_project,
        PackageClass=fake_package_service_class,
        LifecycleClass=fake_lifecycle_service_class,
        ProviderClass=fake_provider_service_class,
    )

    check.is_instance(factory.package, services.PackageService)
    check.is_instance(factory.lifecycle, services.LifecycleService)
    check.is_instance(factory.provider, services.ProviderService)


def test_real_service_error(app_metadata, fake_project):
    factory = services.ServiceFactory(
        app_metadata,
        project=fake_project,
        PackageClass=services.PackageService,
    )

    with pytest.raises(
        TypeError,
        # Python 3.8 doesn't specify the LifecycleService, 3.10 does.
        match=r"(LifecycleService.)?__init__\(\) missing 3 required keyword-only arguments: 'work_dir', 'cache_dir', and 'build_plan'",
    ):
        _ = factory.lifecycle
