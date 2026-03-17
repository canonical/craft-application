# Copyright 2023-2024 Canonical Ltd.
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

from typing import TYPE_CHECKING
from unittest import mock

import pytest
import pytest_check
from craft_application import AppMetadata, services
from craft_cli import emit

if TYPE_CHECKING:
    import pathlib

pytestmark = [
    pytest.mark.filterwarnings("ignore:Registering services on service factory")
]


class FakeService(services.AppService):
    """A fake service for testing."""


@pytest.fixture
def factory(
    tmp_path,
    app_metadata,
    fake_project,
    fake_project_file,
    fake_package_service_class,
    fake_lifecycle_service_class,
):
    services.ServiceFactory.register("package", fake_package_service_class)
    services.ServiceFactory.register("lifecycle", fake_lifecycle_service_class)

    factory = services.ServiceFactory(
        app_metadata,
    )
    factory.update_kwargs(
        "lifecycle",
        work_dir=tmp_path,
        cache_dir=tmp_path / "cache",
        build_plan=[],
    )
    factory.update_kwargs("project", project_dir=fake_project_file.parent)
    return factory


@pytest.mark.parametrize(
    ("service_class", "module"),
    [
        ("ConfigService", "craft_application.services.config"),
        ("InitService", "craft_application.services.init"),
    ],
)
def test_register_service_by_path(service_class, module):
    services.ServiceFactory.register("testy", service_class, module=module)

    service = services.ServiceFactory.get_class("testy")
    pytest_check.equal(service.__module__, module)
    pytest_check.equal(service.__name__, service_class)
    pytest_check.is_(
        service,
        services.ServiceFactory.TestyClass,  # pyright: ignore[reportAttributeAccessIssue]
    )


def test_register_service_by_reference():
    services.ServiceFactory.register("testy", FakeService)

    service = services.ServiceFactory.get_class("testy")
    pytest_check.is_(service, FakeService)
    pytest_check.is_(
        service,
        services.ServiceFactory.TestyClass,  # pyright: ignore[reportAttributeAccessIssue]
    )


def test_register_service_by_path_no_module():
    with pytest.raises(KeyError, match="Must set module"):
        services.ServiceFactory.register("testy", "FakeService")


def test_register_service_by_reference_with_module():
    with pytest.raises(KeyError, match="Must not set module"):
        services.ServiceFactory.register("testy", FakeService, module="__main__")


def test_register_services_in_init(
    app_metadata,
    fake_package_service_class,
    fake_lifecycle_service_class,
    fake_provider_service_class,
):
    factory = services.ServiceFactory(
        app_metadata,
        PackageClass=fake_package_service_class,
        ProviderClass=fake_provider_service_class,
    )

    pytest_check.is_instance(factory.package, fake_package_service_class)
    pytest_check.is_instance(factory.provider, fake_provider_service_class)


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

    services.ServiceFactory.register("package", MockPackageService)
    factory = services.ServiceFactory(app_metadata, project=fake_project)

    with pytest.warns(DeprecationWarning, match="set_kwargs is deprecated"):
        factory.set_kwargs("package", **kwargs)

    check.equal(factory.package, MockPackageService.mock_class.return_value)
    with check:
        MockPackageService.mock_class.assert_called_once_with(
            app=app_metadata, services=factory, **kwargs
        )


@pytest.mark.parametrize(
    ("first_kwargs", "second_kwargs", "expected"),
    [
        ({}, {}, {}),
        (
            {"arg_1": None},
            {"arg_b": "something"},
            {"arg_1": None, "arg_b": "something"},
        ),
        (
            {"overridden": False},
            {"overridden": True},
            {"overridden": True},
        ),
    ],
)
def test_update_kwargs(
    app_metadata,
    fake_project,
    fake_package_service_class,
    first_kwargs,
    second_kwargs,
    check,
    expected,
):
    class MockPackageService(fake_package_service_class):
        mock_class = mock.Mock(return_value=mock.Mock(spec_set=services.PackageService))

        def __new__(cls, *args, **kwargs):
            return cls.mock_class(*args, **kwargs)

    services.ServiceFactory.register("package", MockPackageService)
    factory = services.ServiceFactory(app_metadata, project=fake_project)

    factory.update_kwargs("package", **first_kwargs)
    factory.update_kwargs("package", **second_kwargs)

    check.is_(factory.package, MockPackageService.mock_class.return_value)
    with check:
        MockPackageService.mock_class.assert_called_once_with(
            app=app_metadata, services=factory, **expected
        )


def test_get_class():
    mock_service = mock.Mock(spec=services.AppService)
    services.ServiceFactory.register("test_service", mock_service)

    pytest_check.is_(services.ServiceFactory.get_class("test_service"), mock_service)
    pytest_check.is_(
        services.ServiceFactory.get_class("TestServiceClass"), mock_service
    )
    pytest_check.is_(
        services.ServiceFactory.get_class("TestServiceService"), mock_service
    )


def test_get_class_not_registered():
    with pytest.raises(
        AttributeError, match="Not a registered service: not_registered"
    ):
        services.ServiceFactory.get_class("not_registered")
    with pytest.raises(
        AttributeError, match="Not a registered service: not_registered"
    ):
        services.ServiceFactory.get_class("NotRegisteredService")
    with pytest.raises(
        AttributeError, match="Not a registered service: not_registered"
    ):
        services.ServiceFactory.get_class("NotRegisteredClass")


def test_get_default_services(
    factory, fake_package_service_class, fake_lifecycle_service_class
):
    project_service = factory.get("project")
    pytest_check.is_instance(project_service, services.ProjectService)
    project_service.configure(platform=None, build_for=None)

    pytest_check.is_instance(factory.get("package"), fake_package_service_class)
    pytest_check.is_instance(factory.get("lifecycle"), fake_lifecycle_service_class)
    pytest_check.is_instance(factory.get("config"), services.ConfigService)
    pytest_check.is_instance(factory.get("init"), services.InitService)


def test_get_registered_service(factory):
    factory.register("testy", FakeService)

    first_result = factory.get("testy")
    pytest_check.is_instance(first_result, FakeService)
    pytest_check.is_(first_result, factory.get("testy"))


def test_get_unregistered_service(factory):
    with pytest.raises(
        AttributeError, match="Not a registered service: not_registered"
    ):
        factory.get("not_registered")
    with pytest.raises(
        AttributeError, match="Not a registered service: not_registered"
    ):
        factory.get("NotRegisteredService")
    with pytest.raises(
        AttributeError, match="Not a registered service: not_registered"
    ):
        factory.get("NotRegisteredClass")


def test_get_project_service_error(factory):
    with pytest.raises(RuntimeError, match="Project not configured yet."):
        factory.get("lifecycle")


def test_getattr_cached_service(monkeypatch, factory):
    mock_getattr = mock.Mock(wraps=factory.__getattr__)
    monkeypatch.setattr(services.ServiceFactory, "__getattr__", mock_getattr)
    first = factory.package
    second = factory.package

    assert first is second


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
    fake_project_service_class,
    fake_project_file: pathlib.Path,
):
    services.ServiceFactory.register("project", fake_project_service_class)
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
    factory.update_kwargs("project", project_dir=fake_project_file.parent)
    factory.get("project").configure(platform=None, build_for=None)
    factory.get("project").set(fake_project)  # type: ignore[reportAttributeAccessIssue]

    factory.get("lifecycle")


@pytest.mark.parametrize(
    ("name", "cls"),
    [
        ("PackageClass", services.PackageService),
    ],
)
def test_services_on_instantiation_deprecated(app_metadata, name, cls):
    with pytest.warns(DeprecationWarning, match="Use ServiceFactory.register"):
        services.ServiceFactory(**{"app": app_metadata, name: cls})
