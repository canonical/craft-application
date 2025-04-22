# This file is part of craft-application.
#
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
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Models that describe platforms."""

import enum
import re
from collections.abc import Iterable, Mapping
from typing import ClassVar, get_args

import craft_platforms
import pydantic
from pydantic_core import core_schema as cs
from typing_extensions import Any, Self, TypeVar

from craft_application import errors
from craft_application.models import base
from craft_application.models.constraints import SingleEntryList, UniqueList


class Platform(base.CraftBaseModel):
    """Project platform definition.

    This model defines how a single value under the ``platforms`` key works for a project.
    """

    build_on: UniqueList[str] | str = pydantic.Field(min_length=1)
    build_for: SingleEntryList[str] | str

    @pydantic.field_validator("build_on", "build_for", mode="before")
    @classmethod
    def _vectorise_architectures(cls, values: str | list[str]) -> list[str]:
        """Convert string build-on and build-for to lists."""
        if isinstance(values, str):
            return [values]
        return values

    @pydantic.field_validator("build_on", "build_for", mode="after")
    @classmethod
    def _validate_architectures(cls, values: list[str]) -> list[str]:
        """Validate the architecture entries.

        Entries must be a valid debian architecture or 'all'. Architectures may
        be preceded by an optional base prefix formatted as '[<base>:]<arch>'.

        :raises ValueError: If any of the bases or architectures are not valid.
        """
        [craft_platforms.parse_base_and_architecture(arch) for arch in values]

        return values

    @pydantic.field_validator("build_on", mode="after")
    @classmethod
    def _validate_build_on_real_arch(cls, values: list[str]) -> list[str]:
        """Validate that we must build on a real architecture."""
        for value in values:
            _, arch = craft_platforms.parse_base_and_architecture(value)
            if arch == "all":
                raise ValueError("'all' cannot be used for 'build-on'")
        return values

    @pydantic.model_validator(mode="before")
    @classmethod
    def _validate_platform_set(
        cls, values: Mapping[str, list[str]]
    ) -> Mapping[str, Any]:
        """If build_for is provided, then build_on must also be."""
        # "if values" here ensures that a None value errors properly.
        if values and values.get("build_for") and not values.get("build_on"):
            raise errors.CraftValidationError(
                "'build-for' expects 'build-on' to also be provided."
            )

        return values

    @classmethod
    def from_platforms(cls, platforms: craft_platforms.Platforms) -> dict[str, Self]:
        """Create a dictionary of these objects from craft_platforms PlatformDicts."""
        result: dict[str, Self] = {}
        for key, value in platforms.items():
            name = str(key)
            platform = (
                {"build-on": [name], "build-for": [name]} if value is None else value
            )
            result[name] = cls.model_validate(platform)
        return result


PT = TypeVar("PT", bound=Platform)


class GenericPlatformsDict(dict[str, PT]):
    """A generic dictionary describing the contents of the platforms key.

    This class exists to generate Pydantic and JSON schemas for the platforms key on
    a project. By making it a generic, an application can override the Platform
    definition and provide its own PlatformsDict. A side effect of this, however, is
    that an application cannot simply use the generic directly. Instead, it must create
    a non-generic child class and use that.
    """

    _shorthand_keys: ClassVar[type[enum.Enum] | Iterable[enum.Enum]] = (
        craft_platforms.DebianArchitecture
    )

    @classmethod
    def __get_pydantic_core_schema__(
        cls, source_type: type, handler: pydantic.GetCoreSchemaHandler
    ) -> cs.CoreSchema:
        try:
            (value_type,) = get_args(
                cls.__orig_bases__[0]  # type: ignore[attr-defined]
            )
        except (ValueError, AttributeError):
            raise RuntimeError(
                "Cannot get value type. This likely means the application is using "
                "GenericPlatformsDict directly rather than creating a child class."
            )
        return cs.dict_schema(cs.str_schema(), value_type.__pydantic_core_schema__)

    @classmethod
    def __get_pydantic_json_schema__(
        cls, core_schema: cs.CoreSchema, handler: pydantic.GetJsonSchemaHandler
    ) -> pydantic.json_schema.JsonSchemaValue:
        json_schema = handler(core_schema)
        json_schema = handler.resolve_ref_schema(json_schema)
        arch_pattern_values = "|".join(
            re.escape(key.value) for key in cls._shorthand_keys
        )
        arch_platform_schema = cs.typed_dict_schema(
            {
                "build-on": cs.typed_dict_field(
                    cs.union_schema([cs.str_schema(), cs.list_schema(cs.str_schema())]),
                    required=True,
                ),
                "build-for": cs.typed_dict_field(
                    cs.union_schema([cs.str_schema(), cs.list_schema(cs.str_schema())]),
                    required=False,
                ),
            },
            total=True,
        )
        json_schema["patternProperties"] = {
            f"({arch_pattern_values})": handler(
                cs.union_schema([cs.none_schema(), arch_platform_schema])
            )
        }
        return json_schema


class PlatformsDict(GenericPlatformsDict[Platform]):
    """A dictionary with a pydantic schema for the general platforms key.

    It is a non-generic implementation of GenericPlatformsDict using the default
    Platforms model.
    """
