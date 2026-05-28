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


def test_gets_registered_services(
    check,
    app_metadata,
    project_path,
    fake_project,
    fake_package_service_class,
    fake_lifecycle_service_class,
    fake_provider_service_class,
    fake_project_service_class,
):
    services.ServiceFactory.register("package", fake_package_service_class)
    services.ServiceFactory.register("project", fake_project_service_class)
    services.ServiceFactory.register("lifecycle", fake_lifecycle_service_class)
    services.ServiceFactory.register("provider", fake_provider_service_class)
    factory = services.ServiceFactory(
        app_metadata,
    )
    factory.update_kwargs("project", project_dir=project_path)
    factory.get("project").configure(platform=None, build_for=None)
    factory.get("project").set(fake_project)  # ty: ignore[unresolved-attribute]

    check.is_instance(factory.get("package"), services.PackageService)
    check.is_instance(factory.get("project"), services.ProjectService)
    check.is_instance(factory.get("lifecycle"), services.LifecycleService)
    check.is_instance(factory.get("provider"), services.ProviderService)


def test_real_service_error(app_metadata):
    services.ServiceFactory.register("package", services.PackageService)
    factory = services.ServiceFactory(app_metadata)

    with pytest.raises(
        TypeError,
        # Python 3.8 doesn't specify the LifecycleService, 3.10 does.
        match=r"(LifecycleService.)?__init__\(\) missing 2 required keyword-only arguments: 'work_dir' and 'cache_dir'",
    ):
        _ = factory.lifecycle
