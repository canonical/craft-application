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

from typing import TYPE_CHECKING, Any, Type, cast

import pydantic
import yaml
from yaml.dumper import SafeDumper

from craft_application import errors
from craft_application.util import safe_yaml_load

if TYPE_CHECKING:  # pragma: no cover
    import pathlib

    from typing_extensions import Self


def _alias_generator(s: str) -> str:
    return s.replace("_", "-")


# pyright: reportUnknownMemberType=false
# Type of "represent_scalar" is "(tag: str, value: Unknown, style: str | None = None)
# ->
# ScalarNode" (reportUnknownMemberType)
def _repr_str(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    """Multi-line string representer for the YAML dumper."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


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
            data = safe_yaml_load(file)
        try:
            return cls.unmarshal(data)
        except pydantic.ValidationError as err:
            raise errors.CraftValidationError.from_pydantic(
                err, file_name=path.name
            ) from None

    def to_yaml_file(self, path: pathlib.Path) -> None:
        """Write this model to a YAML file."""
        with path.open("wt") as file:
            yaml.add_representer(
                str, _repr_str, Dumper=cast(Type[yaml.Dumper], yaml.SafeDumper)
            )
            yaml.dump(
                data=self.marshal(), stream=file, Dumper=SafeDumper, sort_keys=False
            )
