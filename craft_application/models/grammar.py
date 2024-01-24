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
from typing import Any, Dict, List, Optional

import pydantic
from craft_grammar.models import (  # type: ignore[import-untyped]
    GrammarSingleEntryDictList,
    GrammarStr,
    GrammarStrList,
)


class _GrammarAwareModel(pydantic.BaseModel):
    class Config:
        """Default configuration for grammar-aware models."""

        validate_assignment = True
        extra = pydantic.Extra.allow  # verify only grammar-aware parts
        alias_generator = lambda s: s.replace(  # noqa: E731 # pyright: ignore[reportUnknownLambdaType, reportUnknownVariableType, reportUnknownMemberType]
            "_", "-"
        )
        allow_population_by_field_name = True


class _GrammarAwarePart(_GrammarAwareModel):
    source: Optional[GrammarStr]
    build_environment: Optional[GrammarSingleEntryDictList]
    build_packages: Optional[GrammarStrList]
    stage_packages: Optional[GrammarStrList]
    build_snaps: Optional[GrammarStrList]
    stage_snaps: Optional[GrammarStrList]
    parse_info: Optional[List[str]]


class GrammarAwareProject(_GrammarAwareModel):
    """Project definition containing grammar-aware components."""

    parts: "Dict[str, _GrammarAwarePart]"

    @classmethod
    def validate_grammar(cls, data: Dict[str, Any]) -> None:
        """Ensure grammar-enabled entries are syntactically valid."""
        cls(**data)
