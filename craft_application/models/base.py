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
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Base pydantic model for *craft applications."""
from __future__ import annotations

import pathlib
from typing import Any, TypeVar

import pydantic
import yaml

from craft_application import errors
from craft_application.util import safe_yaml_load

_ModelType = TypeVar("_ModelType", bound="CraftBaseModel")


def _alias_generator(s: str) -> str:
    return s.replace("_", "-")


class CraftBaseConfig(pydantic.BaseConfig):  # pylint: disable=too-few-public-methods
    """Pydantic model configuration."""

    validate_assignment = True
    extra = pydantic.Extra.forbid
    allow_mutation = True
    allow_population_by_field_name = True
    alias_generator = _alias_generator


class CraftBaseModel(pydantic.BaseModel):
    """Base model for craft-application classes."""

    Config = CraftBaseConfig

    def marshal(self) -> dict[str, str | list[str] | dict[str, Any]]:
        """Convert to a dictionary."""
        return self.dict(by_alias=True, exclude_unset=True)

    @classmethod
    def unmarshal(cls: type[_ModelType], data: dict[str, Any] | Any) -> _ModelType:
        """Create and populate a new model object from dictionary data.

        The unmarshal method validates entries in the input dictionary, populating
        the corresponding fields in the data object.
        :param data: The dictionary data to unmarshal.
        :return: The newly created object.
        :raise TypeError: If data is not a dictionary.
        """
        if not isinstance(data, dict):
            raise TypeError("Project data is not a dictionary")

        return cls(**data)

    @classmethod
    def from_yaml_file(cls: type[_ModelType], path: pathlib.Path) -> _ModelType:
        """Instantiate this model from a YAML file."""
        with path.open() as file:
            data = safe_yaml_load(file)
        try:
            return cls.unmarshal(data)
        except pydantic.ValidationError as err:
            raise errors.CraftValidationError.from_pydantic(err, file_name=path.name)

    def to_yaml_file(self, path: pathlib.Path) -> None:
        """Write this model to a YAML file."""
        with path.open("wt") as file:
            yaml.safe_dump(self.marshal(), file)
