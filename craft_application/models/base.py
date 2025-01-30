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


def alias_generator(s: str) -> str:
    """Generate an alias YAML key."""
    return s.replace("_", "-")


class CraftBaseModel(pydantic.BaseModel):
    """Base model for craft-application classes."""

    model_config = pydantic.ConfigDict(
        validate_assignment=True,
        extra="forbid",
        populate_by_name=True,
        alias_generator=alias_generator,
        coerce_numbers_to_str=True,
    )

    def marshal(self) -> dict[str, str | list[str] | dict[str, Any]]:
        """Convert to a dictionary."""
        return self.model_dump(mode="json", by_alias=True, exclude_unset=True)

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

        return cls.model_validate(data)

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
            cls.transform_pydantic_error(err)
            raise errors.CraftValidationError.from_pydantic(
                err,
                file_name=filepath.name,
                doc_slug=cls.model_reference_slug(),
                logpath_report=False,
            ) from None

    def to_yaml_file(self, path: pathlib.Path) -> None:
        """Write this model to a YAML file."""
        with path.open("wt") as file:
            util.dump_yaml(self.marshal(), stream=file)

    def to_yaml_string(self) -> str:
        """Return this model as a YAML string."""
        return util.dump_yaml(self.marshal())

    @classmethod
    def transform_pydantic_error(cls, error: pydantic.ValidationError) -> None:
        """Modify, in-place, validation errors generated by Pydantic.

        This classmethod is provided as a "hook" for subclasses to perform
        transformations on validation errors specific to their model.

        :param error: The ValidationError generated when trying to create this
          model.
        """

    @classmethod
    def model_reference_slug(cls) -> str | None:
        """Get the slug to this model class' reference docs."""
        return None
