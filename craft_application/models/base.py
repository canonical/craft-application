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
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Base pydantic model for *craft applications."""
from __future__ import annotations

import pathlib
from typing import Any

import pydantic
from typing_extensions import Self

from craft_application import errors, util


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
    def unmarshal(cls, data: dict[str, Any]) -> Self:
        """Create and populate a new model object from dictionary data.

        The unmarshal method validates entries in the input dictionary, populating
        the corresponding fields in the data object.
        :param data: The dictionary data to unmarshal.
        :return: The newly created object.
        :raise TypeError: If data is not a dictionary.
        """
        if not isinstance(data, dict):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise TypeError("Project data is not a dictionary")

        return cls(**data)

    @classmethod
    def from_yaml_file(cls, path: pathlib.Path) -> Self:
        """Instantiate this model from a YAML file."""
        with path.open() as file:
            data = util.safe_yaml_load(file)
        return cls.from_yaml_data(data, path)

    @classmethod
    def from_yaml_data(cls, data: dict[str, Any], filepath: pathlib.Path) -> Self:
        """Instantiate this model from already-loaded YAML data.

        :param data: The dict of model properties.
        :param filepath: The filepath corresponding to ``data``, for error reporting.
        """
        try:
            return cls.unmarshal(data)
        except pydantic.ValidationError as err:
            raise errors.CraftValidationError.from_pydantic(
                err, file_name=filepath.name
            ) from None

    def to_yaml_file(self, path: pathlib.Path) -> None:
        """Write this model to a YAML file."""
        with path.open("wt") as file:
            util.dump_yaml(self.marshal(), stream=file)
