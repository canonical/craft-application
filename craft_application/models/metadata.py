# This file is part of craft-application.
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
"""Base project metadata model."""
import pydantic

from craft_application.models import base


class BaseMetadata(base.CraftBaseModel):
    """Project metadata base model.

    This model is the basis for output metadata files that are stored in
    the application's output.
    """

    model_config = pydantic.ConfigDict(
        validate_assignment=True,
        extra="allow",
        populate_by_name=True,
        alias_generator=base.alias_generator,
    )
