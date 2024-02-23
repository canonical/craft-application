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
"""Tests for ServiceFactory"""
from __future__ import annotations

from unittest import mock

import pytest
import pytest_check
from craft_application import AppMetadata, services
from craft_cli import emit


@pytest.fixture()
def factory(
    app_metadata, fake_project, fake_package_service_class, fake_lifecycle_service_class
):
    return services.ServiceFactory(
        app_metadata,
        project=fake_project,
        PackageClass=fake_package_service_class,
        LifecycleClass=fake_lifecycle_service_class,
    )


def test_correct_init(
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

    pytest_check.is_instance(factory.package, services.PackageService)
    pytest_check.is_instance(factory.lifecycle, services.LifecycleService)
    pytest_check.is_instance(factory.provider, services.ProviderService)


@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"arg_1": None, "arg_b": "something"},
    ],
)
def test_set_kwargs(
    app_metadata, fake_project, check, fake_package_service_class, kwargs
):
    class MockPackageService(fake_package_service_class):
        mock_class = mock.Mock(return_value=mock.Mock(spec_set=services.PackageService))

        def __new__(cls, *args, **kwargs):
            return cls.mock_class(*args, **kwargs)

    factory = services.ServiceFactory(
        app_metadata, project=fake_project, PackageClass=MockPackageService
    )

    factory.set_kwargs("package", **kwargs)

    check.equal(factory.package, MockPackageService.mock_class.return_value)
    with check:
        MockPackageService.mock_class.assert_called_once_with(
            app=app_metadata, services=factory, project=fake_project, **kwargs
        )


def test_getattr_cached_service(monkeypatch, check, factory):
    mock_getattr = mock.Mock(wraps=factory.__getattr__)
    monkeypatch.setattr(services.ServiceFactory, "__getattr__", mock_getattr)
    first = factory.package
    second = factory.package

    check.is_(first, second)
    # Only gets called once because the second time `package` is an instance attribute.
    with check:
        mock_getattr.assert_called_once_with("package")


def test_getattr_not_a_class(factory):
    with pytest.raises(AttributeError):
        _ = factory.invalid_name


def test_getattr_not_a_service_class(app_metadata, fake_project):
    class InvalidClass:
        pass

    factory = services.ServiceFactory(
        app_metadata,
        project=fake_project,
        # This incorrect type is intentional
        PackageClass=InvalidClass,  # pyright: ignore[reportArgumentType]
    )

    with pytest.raises(TypeError):
        _ = factory.package


def test_getattr_project_none(app_metadata, fake_package_service_class):
    factory = services.ServiceFactory(
        app_metadata, PackageClass=fake_package_service_class
    )

    with pytest.raises(
        ValueError,
        match="^FakePackageService requires a project to be available before creation.$",
    ):
        _ = factory.package


def test_service_setup(app_metadata, fake_project, fake_package_service_class, emitter):
    class FakePackageService(fake_package_service_class):
        def setup(self) -> None:
            emit.debug("setting up package service")

    factory = services.ServiceFactory(
        app_metadata, project=fake_project, PackageClass=FakePackageService
    )
    _ = factory.package

    assert emitter.assert_debug("setting up package service")


def test_mandatory_adoptable_field(
    fake_project,
    fake_lifecycle_service_class,
    fake_package_service_class,
):
    app_metadata = AppMetadata(
        "testcraft",
        "A fake app for testing craft-application",
        mandatory_adoptable_fields=["license"],
    )
    fake_project.license = None
    fake_project.adopt_info = "partname"

    factory = services.ServiceFactory(
        app_metadata,
        project=fake_project,
        PackageClass=fake_package_service_class,
        LifecycleClass=fake_lifecycle_service_class,
    )

    _ = factory.lifecycle
