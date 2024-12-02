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
"""Factory class for lazy-loading service classes."""
from __future__ import annotations

import dataclasses
import importlib
import re
import warnings
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypeVar, cast, overload

import annotated_types

from craft_application import models, services

if TYPE_CHECKING:
    from craft_application.application import AppMetadata

_service_classes: dict[str, tuple[str, str] | type[services.AppService]] = {}
_DEFAULT_SERVICES = {
    "config": "ConfigService",
    "fetch": "FetchService",
    "init": "InitService",
    "lifecycle": "LifecycleService",
    "provider": "ProviderService",
    "remote_build": "RemoteBuildService",
    "request": "RequestService",
}
_CAMEL_TO_PYTHON_CASE_REGEX = re.compile(r"(?<!^)(?=[A-Z])")

T = TypeVar("T")
_ClassName = Annotated[str, annotated_types.Predicate(lambda x: x.endswith("Class"))]


@dataclasses.dataclass(init=False)
class ServiceFactory:
    """Factory class for lazy-loading service classes.

    This class and its subclasses allow a craft application to only load the
    relevant services for the command that is being run.

    This factory is intended to be extended with various additional service classes
    and possibly have its existing service classes overridden.
    """

    def __init__(  # noqa: PLR0913
        self,
        app: AppMetadata,
        # Ignoring N803 because these argument names are previously created.
        PackageClass: type[services.PackageService] | None = None,  # noqa: N803
        LifecycleClass: type[services.LifecycleService] | None = None,  # noqa: N803
        ProviderClass: type[services.ProviderService] | None = None,  # noqa: N803
        RemoteBuildClass: type[services.RemoteBuildService] | None = None,  # noqa: N803
        RequestClass: type[services.RequestService] | None = None,  # noqa: N803
        ConfigClass: type[services.ConfigService] | None = None,  # noqa: N803
        FetchClass: type[services.FetchService] | None = None,  # noqa: N803
        InitClass: type[services.InitService] | None = None,  # noqa: N803
        project: models.Project | None = None,
    ) -> None:
        self.app = app
        self.project = project
        self._service_kwargs: dict[str, dict[str, Any]] = {}
        self._services: dict[str, services.AppService] = {}

        # Backwards compatibility for assigning service classes on initialisation.
        if PackageClass:
            warnings.warn(
                f'Registering services on service factory instantiation is deprecated. Use ServiceFactory.register("package", {PackageClass.__name__}) instead.',
                category=DeprecationWarning,
                stacklevel=2,
            )
            self.register("package", PackageClass)
        if LifecycleClass:
            warnings.warn(
                DeprecationWarning(
                    f'Registering services on service factory instantiation is deprecated. Use ServiceFactory.register("lifecycle", {LifecycleClass.__name__}) instead.'
                ),
                stacklevel=2,
            )
            self.register("lifecycle", LifecycleClass)
        if ProviderClass:
            warnings.warn(
                DeprecationWarning(
                    f'Registering services on service factory instantiation is deprecated. Use ServiceFactory.register("provider", {ProviderClass.__name__}) instead.'
                ),
                stacklevel=2,
            )
            self.register("provider", ProviderClass)
        if RemoteBuildClass:
            warnings.warn(
                DeprecationWarning(
                    f'Registering services on service factory instantiation is deprecated. Use ServiceFactory.register("remote_build", {RemoteBuildClass.__name__}) instead.'
                ),
                stacklevel=2,
            )
            self.register("remote_build", RemoteBuildClass)
        if RequestClass:
            warnings.warn(
                DeprecationWarning(
                    f'Registering services on service factory instantiation is deprecated. Use ServiceFactory.register("request", {RequestClass.__name__}) instead.'
                ),
                stacklevel=2,
            )
            self.register("request", RequestClass)
        if ConfigClass:
            warnings.warn(
                DeprecationWarning(
                    f'Registering services on service factory instantiation is deprecated. Use ServiceFactory.register("config", {ConfigClass.__name__}) instead.'
                ),
                stacklevel=2,
            )
            self.register("config", ConfigClass)
        if FetchClass:
            warnings.warn(
                DeprecationWarning(
                    f'Registering services on service factory instantiation is deprecated. Use ServiceFactory.register("fetch", {FetchClass.__name__}) instead.'
                ),
                stacklevel=2,
            )
            self.register("fetch", FetchClass)
        if InitClass:
            warnings.warn(
                DeprecationWarning(
                    f'Registering services on service factory instantiation is deprecated. Use ServiceFactory.register("init", {InitClass.__name__}) instead.'
                ),
                stacklevel=2,
            )
            self.register("init", InitClass)

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
            _service_classes[name] = (module, service_class)
        else:
            if module is not None:
                raise KeyError(
                    "Must not set module if service_class is passed by value."
                )
            _service_classes[name] = service_class

    @classmethod
    def reset(cls) -> None:
        """Reset the registered services."""
        _service_classes.clear()
        for name, class_name in _DEFAULT_SERVICES.items():
            cls.register(name, class_name, module=f"craft_application.services.{name}")

    def set_kwargs(
        self,
        service: str,
        **kwargs: Any,  # noqa: ANN401 this is intentionally duck-typed.
    ) -> None:
        """Set up the keyword arguments to pass to a particular service class.

        PENDING DEPRECATION: use update_kwargs instead
        """
        warnings.warn(
            PendingDeprecationWarning(
                "ServiceFactory.set_kwargs is pending deprecation. Use update_kwargs instead."
            ),
            stacklevel=2,
        )
        self._service_kwargs[service] = kwargs

    def update_kwargs(
        self,
        service: str,
        **kwargs: Any,  # noqa: ANN401 this is intentionally duck-typed.
    ) -> None:
        """Update the keyword arguments to pass to a particular service class.

        This works like ``dict.update()``, overwriting already-set values.

        :param service: the name of the service (e.g. "lifecycle")
        :param kwargs: keyword arguments to set.
        """
        self._service_kwargs.setdefault(service, {}).update(kwargs)

    @overload
    def get_service_class(
        self, name: Literal["config", "ConfigService", "ConfigClass"]
    ) -> type[services.ConfigService]: ...
    @overload
    def get_service_class(
        self, name: Literal["fetch", "FetchService", "FetchClass"]
    ) -> type[services.FetchService]: ...
    @overload
    def get_service_class(
        self, name: Literal["init", "InitService", "InitClass"]
    ) -> type[services.InitService]: ...
    @overload
    def get_service_class(
        self, name: Literal["lifecycle", "LifecycleService", "LifecycleClass"]
    ) -> type[services.LifecycleService]: ...
    @overload
    def get_service_class(
        self, name: Literal["package", "PackageService", "PackageClass"]
    ) -> type[services.PackageService]: ...
    @overload
    def get_service_class(
        self, name: Literal["provider", "ProviderService", "ProviderClass"]
    ) -> type[services.ProviderService]: ...
    @overload
    def get_service_class(
        self, name: Literal["remote_build", "RemoteBuildService", "RemoteBuildClass"]
    ) -> type[services.RemoteBuildService]: ...
    @overload
    def get_service_class(
        self, name: Literal["request", "RequestService", "RequestClass"]
    ) -> type[services.RequestService]: ...
    @overload
    def get_service_class(self, name: str) -> type[services.AppService]: ...
    def get_service_class(self, name: str) -> type[services.AppService]:
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
        classes = dataclasses.asdict(self)
        if service in _service_classes:  # Try registered services first.
            service_info = _service_classes[service]
            if isinstance(service_info, tuple):
                module_name, class_name = service_info
                module = importlib.import_module(module_name)
                return cast(type[services.AppService], getattr(module, class_name))
            return service_info
        if service_cls_name in classes and classes[service_cls_name] is not None:
            return cast(type[services.AppService], getattr(self, service_cls_name))
        raise AttributeError(service)

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
    def get(self, service: Literal["provider"]) -> services.ProviderService: ...
    @overload
    def get(self, service: Literal["remote_build"]) -> services.RemoteBuildService: ...
    @overload
    def get(self, service: Literal["request"]) -> services.RequestService: ...
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
        cls = self.get_service_class(service)
        kwargs = self._service_kwargs.get(service, {})
        if issubclass(cls, services.ProjectService):
            if not self.project:
                raise ValueError(
                    f"{cls.__name__} requires a project to be available before creation."
                )
            kwargs.setdefault("project", self.project)

        instance = cls(app=self.app, services=self, **kwargs)
        instance.setup()
        self._services[service] = instance
        return instance

    # Ignores here are due to: https://github.com/python/mypy/issues/8203
    @overload
    def __getattr__(self, name: Literal["ConfigClass"]) -> type[services.ConfigService]: ...  # type: ignore[misc]
    @overload
    def __getattr__(self, name: Literal["config"]) -> services.ConfigService: ...  # type: ignore[misc]
    @overload
    def __getattr__(self, name: Literal["FetchClass"]) -> type[services.FetchService]: ...  # type: ignore[misc]
    @overload
    def __getattr__(self, name: Literal["fetch"]) -> services.FetchService: ...  # type: ignore[misc]
    @overload
    def __getattr__(self, name: Literal["InitClass"]) -> type[services.InitService]: ...  # type: ignore[misc]
    @overload
    def __getattr__(self, name: Literal["init"]) -> services.InitService: ...  # type: ignore[misc]
    @overload
    def __getattr__(self, name: Literal["PackageClass"]) -> type[services.PackageService]: ...  # type: ignore[misc]
    @overload
    def __getattr__(self, name: Literal["package"]) -> services.PackageService: ...  # type: ignore[misc]
    @overload
    def __getattr__(self, name: Literal["LifecycleClass"]) -> type[services.LifecycleService]: ...  # type: ignore[misc]
    @overload
    def __getattr__(  # type: ignore[misc]
        self, name: Literal["lifecycle"]
    ) -> services.LifecycleService: ...
    @overload
    def __getattr__(self, name: Literal["ProviderClass"]) -> type[services.ProviderService]: ...  # type: ignore[misc]
    @overload
    def __getattr__(self, name: Literal["provider"]) -> services.ProviderService: ...  # type: ignore[misc]
    @overload
    def __getattr__(self, name: Literal["RemoteBuildClass"]) -> type[services.RemoteBuildService]: ...  # type: ignore[misc]
    @overload
    def __getattr__(  # type: ignore[misc]
        self, name: Literal["remote_build"]
    ) -> services.RemoteBuildService: ...
    @overload
    def __getattr__(self, name: Literal["RequestClass"]) -> type[services.RequestService]: ...  # type: ignore[misc]
    @overload
    def __getattr__(self, name: Literal["request"]) -> services.RequestService: ...  # type: ignore[misc]
    @overload
    def __getattr__(self, name: _ClassName) -> type[services.AppService]: ...  # type: ignore[misc]
    @overload
    def __getattr__(self, name: str) -> services.AppService: ...  # type: ignore[misc]
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
        if name.endswith("Class"):
            result = self.get_service_class(name)
        else:
            result = self.get(name)
        setattr(self, name, result)
        return result


ServiceFactory.reset()  # Set up default services.
