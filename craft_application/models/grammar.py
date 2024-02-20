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

"""Grammar-aware project for *craft applications."""
from typing import Any

import pydantic
from craft_grammar.models import (  # type: ignore[import-untyped]
    GrammarSingleEntryDictList,
    GrammarStr,
    GrammarStrList,
)

from craft_application.models.base import alias_generator


class _GrammarAwareModel(pydantic.BaseModel):
    class Config:
        """Default configuration for grammar-aware models."""

        validate_assignment = True
        extra = pydantic.Extra.allow  # verify only grammar-aware parts
        alias_generator = alias_generator
        allow_population_by_field_name = True


class _GrammarAwarePart(_GrammarAwareModel):
    source: GrammarStr | None
    build_environment: GrammarSingleEntryDictList | None
    build_packages: GrammarStrList | None
    stage_packages: GrammarStrList | None
    build_snaps: GrammarStrList | None
    stage_snaps: GrammarStrList | None
    parse_info: list[str] | None


class GrammarAwareProject(_GrammarAwareModel):
    """Project definition containing grammar-aware components."""

    parts: "dict[str, _GrammarAwarePart]"

    @classmethod
    def validate_grammar(cls, data: dict[str, Any]) -> None:
        """Ensure grammar-enabled entries are syntactically valid."""
        cls(**data)
