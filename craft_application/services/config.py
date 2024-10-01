#  This file is part of craft-application.
#
#  Copyright 2024 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Configuration service."""
from __future__ import annotations

import abc
import contextlib
import enum
import os
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, TypeVar, cast, final

import pydantic
import pydantic_core
import snaphelpers
from craft_cli import emit
from typing_extensions import override

from craft_application import _config, application, util
from craft_application.services import base

if TYPE_CHECKING:
    from craft_application.services.service_factory import ServiceFactory


T = TypeVar("T")


class ConfigHandler(abc.ABC):
    """An abstract class for configuration handlers."""

    def __init__(self, app: application.AppMetadata) -> None:
        self._app = app

    @abc.abstractmethod
    def get_raw(self, item: str) -> Any:  # noqa: ANN401
        """Get the string value for a configuration item.

        :param item: the name of the configuration item.
        :returns: The raw value of the item.
        :raises: KeyError if the item cannot be found.
        """


@final
class AppEnvironmentHandler(ConfigHandler):
    """Configuration handler to get values from app-specific environment variables."""

    def __init__(self, app: application.AppMetadata) -> None:
        super().__init__(app)
        self._environ_prefix = f"{app.name.upper()}"

    @override
    def get_raw(self, item: str) -> str:
        return os.environ[f"{self._environ_prefix}_{item.upper()}"]


@final
class CraftEnvironmentHandler(ConfigHandler):
    """Configuration handler to get values from CRAFT environment variables."""

    def __init__(self, app: application.AppMetadata) -> None:
        super().__init__(app)
        self._fields = _config.ConfigModel.model_fields

    @override
    def get_raw(self, item: str) -> str:
        # Ensure that CRAFT_* env vars can only be used for configuration items
        # known to craft-application.
        if item not in self._fields:
            raise KeyError(f"{item!r} not a general craft-application config item.")

        return os.environ[f"CRAFT_{item.upper()}"]


class SnapConfigHandler(ConfigHandler):
    """Configuration handler that gets values from snap."""

    def __init__(self, app: application.AppMetadata) -> None:
        super().__init__(app)
        if not snaphelpers.is_snap():
            raise OSError("Not running as a snap.")
        try:
            self._snap = snaphelpers.SnapConfig()
        except KeyError:
            raise OSError("Not running as a snap.")
        except snaphelpers.SnapCtlError:
            # Most likely to happen in a container that has the snap environment set.
            # See: https://github.com/canonical/snapcraft/issues/5079
            emit.progress(
                "Snap environment is set, but cannot connect to snapd. "
                "Snap configuration is unavailable.",
                permanent=True,
            )
            raise OSError("Not running as a snap or with snapd disabled.")

    @override
    def get_raw(self, item: str) -> Any:
        snap_item = item.replace("_", "-")
        try:
            return self._snap.get(snap_item)
        except snaphelpers.UnknownConfigKey as exc:
            raise KeyError(f"unknown snap config item: {item!r}") from exc


@final
class DefaultConfigHandler(ConfigHandler):
    """Configuration handler for getting default values."""

    def __init__(self, app: application.AppMetadata) -> None:
        super().__init__(app)
        self._config_model = app.ConfigModel
        self._cache: dict[str, str] = {}

    @override
    def get_raw(self, item: str) -> Any:
        if item in self._cache:
            return self._cache[item]

        field = self._config_model.model_fields[item]
        if field.default is not pydantic_core.PydanticUndefined:
            self._cache[item] = field.default
            return field.default
        if field.default_factory is not None:
            default = field.default_factory()
            self._cache[item] = default
            return default

        raise KeyError(f"config item {item!r} has no default value.")


class ConfigService(base.AppService):
    """Application-wide configuration access."""

    _handlers: list[ConfigHandler]

    def __init__(
        self,
        app: application.AppMetadata,
        services: ServiceFactory,
        *,
        extra_handlers: Iterable[type[ConfigHandler]] = (),
    ) -> None:
        super().__init__(app, services)
        self._extra_handlers = extra_handlers
        self._default_handler = DefaultConfigHandler(self._app)

    @override
    def setup(self) -> None:
        super().setup()
        self._handlers = [
            AppEnvironmentHandler(self._app),
            CraftEnvironmentHandler(self._app),
            *(handler(self._app) for handler in self._extra_handlers),
        ]
        try:
            snap_handler = SnapConfigHandler(self._app)
        except OSError:
            emit.debug(
                "App is not running as a snap - snap config handler not created."
            )
        else:
            self._handlers.append(snap_handler)

    def get(self, item: str) -> Any:  # noqa: ANN401
        """Get the given configuration item."""
        if item not in self._app.ConfigModel.model_fields:
            raise KeyError(r"unknown config item: {item!r}")
        field_info = self._app.ConfigModel.model_fields[item]

        for handler in self._handlers:
            try:
                value = handler.get_raw(item)
            except KeyError:
                continue
            else:
                break
        else:
            return self._default_handler.get_raw(item)

        return self._convert_type(value, field_info.annotation)  # type: ignore[arg-type,return-value]

    def _convert_type(self, value: str, field_type: type[T]) -> T:
        """Convert the value to the appropriate type."""
        if isinstance(field_type, type):
            if issubclass(field_type, str):
                return cast(T, field_type(value))
            if issubclass(field_type, bool):
                return cast(T, util.strtobool(value))
            if issubclass(field_type, enum.Enum):
                with contextlib.suppress(KeyError):
                    return cast(T, field_type[value])
                with contextlib.suppress(KeyError):
                    return cast(T, field_type[value.upper()])
        field_adapter = pydantic.TypeAdapter(field_type)
        return field_adapter.validate_strings(value)
