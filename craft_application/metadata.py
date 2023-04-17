# Copyright 2023 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Base project metadata model."""
from overrides import overrides
from pydantic_yaml import YamlModel


class MetadataModel(YamlModel):
    """Project metadata base model.

    This model is the basis for output metadata files that are stored in
    the application's output.
    """

    class Config:  # pylint: disable=too-few-public-methods
        """Pydantic model configuration."""

        allow_population_by_field_name = True
        alias_generator = lambda s: s.replace("_", "-")  # noqa: E731

    @overrides
    def yaml(self) -> str:
        """Generate a YAML representation of the model."""
        return super().yaml(
            by_alias=True,
            exclude_none=True,
            allow_unicode=True,
            sort_keys=False,
            width=1000,
        )
