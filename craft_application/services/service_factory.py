# Copyright 2023-2025 Canonical Ltd.
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
"""Factory class for lazy-loading service classes."""

from __future__ import annotations

import importlib
import re
import warnings
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Literal,
    TypeVar,
    cast,
    overload,
)

import annotated_types

from craft_application import services

if TYPE_CHECKING:
    from craft_application.application import AppMetadata
    from craft_application.services.buildplan import BuildPlanService
    from craft_application.services.project import ProjectService

_DEFAULT_SERVICES = {
    "build_plan": "BuildPlanService",
    "config": "ConfigService",
    "fetch": "FetchService",
    "init": "InitService",
    "lifecycle": "LifecycleService",
    "project": "ProjectService",
    "provider": "ProviderService",
    "remote_build": "RemoteBuildService",
    "state": "StateService",
    "request": "RequestService",
    "testing": "TestingService",
}
_CAMEL_TO_PYTHON_CASE_REGEX = re.compile(r"(?<!^)(?=[A-Z])")

T = TypeVar("T")
_ClassName = Annotated[str, annotated_types.Predicate(lambda x: x.endswith("Class"))]


class ServiceFactory:
    """Factory class for lazy-loading service classes.

    This class and its subclasses allow a craft application to only load the
    relevant services for the command that is being run.

    This factory is intended to be extended with various additional service classes
    and possibly have its existing service classes overridden.
    """

    _service_classes: ClassVar[
        dict[str, tuple[str, str] | type[services.AppService]]
    ] = {}

    if TYPE_CHECKING:
        # Cheeky hack that lets static type checkers report the correct types.
        # This does not need any new types added as the ``__getattr__`` method is
        # deprecated and we should encourage using ``get()`` instead.
        package: services.PackageService
        lifecycle: services.LifecycleService
        provider: services.ProviderService
        remote_build: services.RemoteBuildService
        request: services.RequestService
        config: services.ConfigService
        fetch: services.FetchService
        init: services.InitService
        testing: services.TestingService
        state: services.StateService

    def __init__(
        self,
        app: AppMetadata,
        **kwargs: type[services.AppService] | None,
    ) -> None:
        self.app = app
        self._service_kwargs: dict[str, dict[str, Any]] = {}
        self._services: dict[str, services.AppService] = {}

        for cls_name, value in kwargs.items():
            if cls_name.endswith("Class"):
                if value is not None:
                    identifier = _CAMEL_TO_PYTHON_CASE_REGEX.sub(
                        "_", cls_name[:-5]
                    ).lower()
                    warnings.warn(
                        f'Registering services on service factory instantiation is deprecated. Use ServiceFactory.register("{identifier}", {value.__name__}) instead.',
                        category=DeprecationWarning,
                        stacklevel=3,
                    )
                    self.register(identifier, value)
                setattr(self, cls_name, self.get_class(cls_name))

        if "package" not in self._service_classes:
            raise TypeError(
                "A PackageService must be registered before creating the ServiceFactory."
            )

    @classmethod
    def register(
        cls,
        name: str,
        service_class: type[services.AppService] | str,
        *,
        module: str | None = None,
    ) -> None:
        """Register a service class with a given name.

        :param name: the name to call the service class.
        :param service_class: either a service class or a string that names the service
            class.
        :param module: If service_class is a string, the module from which to import
            the service class.
        """
        if isinstance(service_class, str):
            if module is None:
                raise KeyError("Must set module if service_class is set by name.")
            cls._service_classes[name] = (module, service_class)
        else:
            if module is not None:
                raise KeyError(
                    "Must not set module if service_class is passed by value."
                )
            cls._service_classes[name] = service_class

        # For backwards compatibility with class attribute service types.
        service_cls_name = "".join(word.title() for word in name.split("_")) + "Class"
        setattr(cls, service_cls_name, cls.get_class(name))

    @classmethod
    def reset(cls) -> None:
        """Reset the registered services."""
        cls._service_classes.clear()
        for name, class_name in _DEFAULT_SERVICES.items():
            module_name = name.replace("_", "")
            cls.register(
                name, class_name, module=f"craft_application.services.{module_name}"
            )

    def set_kwargs(
        self,
        service: str,
        **kwargs: Any,
    ) -> None:
        """Set up the keyword arguments to pass to a particular service class.

        DEPRECATED: use update_kwargs instead
        """
        warnings.warn(
            DeprecationWarning(
                "ServiceFactory.set_kwargs is deprecated. Use update_kwargs instead."
            ),
            stacklevel=2,
        )
        self._service_kwargs[service] = kwargs

    def update_kwargs(
        self,
        service: str,
        **kwargs: Any,
    ) -> None:
        """Update the keyword arguments to pass to a particular service class.

        This works like ``dict.update()``, overwriting already-set values.

        :param service: the name of the service (e.g. "lifecycle")
        :param kwargs: keyword arguments to set.
        """
        self._service_kwargs.setdefault(service, {}).update(kwargs)

    @overload
    @classmethod
    def get_class(
        cls, name: Literal["build_plan", "BuildPlanService", "BuildPlanClass"]
    ) -> type[BuildPlanService]: ...
    @overload
    @classmethod
    def get_class(
        cls, name: Literal["config", "ConfigService", "ConfigClass"]
    ) -> type[services.ConfigService]: ...
    @overload
    @classmethod
    def get_class(
        cls, name: Literal["fetch", "FetchService", "FetchClass"]
    ) -> type[services.FetchService]: ...
    @overload
    @classmethod
    def get_class(
        cls, name: Literal["init", "InitService", "InitClass"]
    ) -> type[services.InitService]: ...
    @overload
    @classmethod
    def get_class(
        cls, name: Literal["lifecycle", "LifecycleService", "LifecycleClass"]
    ) -> type[services.LifecycleService]: ...
    @overload
    @classmethod
    def get_class(
        cls, name: Literal["package", "PackageService", "PackageClass"]
    ) -> type[services.PackageService]: ...
    @overload
    @classmethod
    def get_class(
        cls, name: Literal["provider", "ProviderService", "ProviderClass"]
    ) -> type[services.ProviderService]: ...
    @overload
    @classmethod
    def get_class(
        cls, name: Literal["remote_build", "RemoteBuildService", "RemoteBuildClass"]
    ) -> type[services.RemoteBuildService]: ...
    @overload
    @classmethod
    def get_class(
        cls, name: Literal["request", "RequestService", "RequestClass"]
    ) -> type[services.RequestService]: ...
    @overload
    @classmethod
    def get_class(
        cls, name: Literal["state", "StateService", "StateClass"]
    ) -> type[services.StateService]: ...
    @overload
    @classmethod
    def get_class(
        cls, name: Literal["testing", "TestingService", "TestingClass"]
    ) -> type[services.TestingService]: ...
    @overload
    @classmethod
    def get_class(cls, name: str) -> type[services.AppService]: ...
    @classmethod
    def get_class(cls, name: str) -> type[services.AppService]:
        """Get the class for a service by its name."""
        if name.endswith("Class"):
            service_cls_name = name
            service = _CAMEL_TO_PYTHON_CASE_REGEX.sub("_", name[:-5]).lower()
        elif name.endswith("Service"):
            service = _CAMEL_TO_PYTHON_CASE_REGEX.sub("_", name[:-7]).lower()
            service_cls_name = name[:-7] + "Class"
        else:
            service_cls_name = "".join(word.title() for word in name.split("_"))
            service_cls_name += "Class"
            service = name
        if service not in cls._service_classes:
            raise AttributeError(f"Not a registered service: {service}")
        service_info = cls._service_classes[service]
        if isinstance(service_info, tuple):
            module_name, class_name = service_info
            module = importlib.import_module(module_name)
            return cast(type[services.AppService], getattr(module, class_name))
        return service_info

    @overload
    def get(self, service: Literal["build_plan"]) -> BuildPlanService: ...
    @overload
    def get(self, service: Literal["config"]) -> services.ConfigService: ...
    @overload
    def get(self, service: Literal["fetch"]) -> services.FetchService: ...
    @overload
    def get(self, service: Literal["init"]) -> services.InitService: ...
    @overload
    def get(self, service: Literal["package"]) -> services.PackageService: ...
    @overload
    def get(self, service: Literal["lifecycle"]) -> services.LifecycleService: ...
    @overload
    def get(self, service: Literal["project"]) -> ProjectService: ...
    @overload
    def get(self, service: Literal["provider"]) -> services.ProviderService: ...
    @overload
    def get(self, service: Literal["remote_build"]) -> services.RemoteBuildService: ...
    @overload
    def get(self, service: Literal["request"]) -> services.RequestService: ...
    @overload
    def get(self, service: Literal["state"]) -> services.StateService: ...
    @overload
    def get(self, service: Literal["testing"]) -> services.TestingService: ...
    @overload
    def get(self, service: str) -> services.AppService: ...
    def get(self, service: str) -> services.AppService:
        """Get a service by name.

        :param service: the name of the service (e.g. "config")
        :returns: An instantiated and set up service class.

        Also caches the service so as to provide a single service instance per
        ServiceFactory.
        """
        if service in self._services:
            return self._services[service]
        cls = self.get_class(service)
        kwargs = self._service_kwargs.get(service, {})
        instance = cls(app=self.app, services=self, **kwargs)
        instance.setup()
        self._services[service] = instance
        return instance

    def __getattr__(self, name: str) -> services.AppService | type[services.AppService]:
        """Instantiate a service class.

        This allows us to lazy-load only the necessary services whilst still
        treating them as attributes of our factory in a dynamic manner.
        For a service (e.g. ``package``, the PackageService instance) that has not
        been instantiated, this method finds the corresponding class, instantiates
        it with defaults and any values set using ``set_kwargs``, and stores the
        instantiated service as an instance attribute, allowing the same service
        instance to be reused for the entire run of the application.
        """
        result = self.get_class(name) if name.endswith("Class") else self.get(name)
        setattr(self, name, result)
        return result


ServiceFactory.reset()  # Set up default services on import.
