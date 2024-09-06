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
import warnings
from typing import TYPE_CHECKING, Any

from craft_application import models, services

if TYPE_CHECKING:
    from craft_application.application import AppMetadata


@dataclasses.dataclass
class ServiceFactory:
    """Factory class for lazy-loading service classes.

    This class and its subclasses allow a craft application to only load the
    relevant services for the command that is being run.

    This factory is intended to be extended with various additional service classes
    and possibly have its existing service classes overridden.
    """

    app: AppMetadata

    PackageClass: type[services.PackageService]
    LifecycleClass: type[services.LifecycleService] = services.LifecycleService
    ProviderClass: type[services.ProviderService] = services.ProviderService
    RemoteBuildClass: type[services.RemoteBuildService] = services.RemoteBuildService
    RequestClass: type[services.RequestService] = services.RequestService
    ConfigClass: type[services.ConfigService] = services.ConfigService

    project: models.Project | None = None

    if TYPE_CHECKING:
        # Cheeky hack that lets static type checkers report the correct types.
        # Any apps that add their own services should do this too.
        package: services.PackageService = None  # type: ignore[assignment]
        lifecycle: services.LifecycleService = None  # type: ignore[assignment]
        provider: services.ProviderService = None  # type: ignore[assignment]
        remote_build: services.RemoteBuildService = None  # type: ignore[assignment]
        request: services.RequestService = None  # type: ignore[assignment]
        config: services.ConfigService = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self._service_kwargs: dict[str, dict[str, Any]] = {}

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

    def __getattr__(self, service: str) -> services.AppService:
        """Instantiate a service class.

        This allows us to lazy-load only the necessary services whilst still
        treating them as attributes of our factory in a dynamic manner.
        For a service (e.g. ``package``, the PackageService instance) that has not
        been instantiated, this method finds the corresponding class, instantiates
        it with defaults and any values set using ``set_kwargs``, and stores the
        instantiated service as an instance attribute, allowing the same service
        instance to be reused for the entire run of the application.
        """
        service_cls_name = "".join(word.title() for word in service.split("_"))
        service_cls_name += "Class"
        classes = dataclasses.asdict(self)
        if service_cls_name not in classes:
            raise AttributeError(service)
        cls = getattr(self, service_cls_name)
        if not issubclass(cls, services.AppService):
            raise TypeError(f"{cls.__name__} is not a service class")
        kwargs = self._service_kwargs.get(service, {})
        if issubclass(cls, services.ProjectService):
            if not self.project:
                raise ValueError(
                    f"{cls.__name__} requires a project to be available before creation."
                )
            kwargs.setdefault("project", self.project)

        instance: services.AppService = cls(app=self.app, services=self, **kwargs)
        instance.setup()
        setattr(self, service, instance)
        return instance
