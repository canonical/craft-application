# This file is part of craft-application.
#
# Copyright 2023-2024 Canonical Ltd.
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
"""Grammar-aware Project model."""

from typing import Any

import pydantic

from ._base import _GrammarAwareModel
from ._parts import _GrammarAwarePart
from ._repo import _GrammarRepositoryTypes


class GrammarAwareProject(_GrammarAwareModel):
    """Project definition containing grammar-aware components."""

    parts: "dict[str, _GrammarAwarePart]"
    package_repositories: list[_GrammarRepositoryTypes] | None = None

    @pydantic.root_validator(  # pyright: ignore[reportUntypedFunctionDecorator,reportUnknownMemberType]
        pre=True
    )
    def _ensure_parts(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Ensure that the "parts" dictionary exists.

        Some models (e.g. charmcraft) have this as optional. If there is no `parts`
        item defined, set it to an empty dictionary. This is distinct from having
        `parts` be invalid, which is not coerced here.
        """
        data.setdefault("parts", {})
        return data

    @classmethod
    def validate_grammar(cls, data: dict[str, Any]) -> None:
        """Ensure grammar-enabled entries are syntactically valid."""
        cls(**data)
