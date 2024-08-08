# This file is part of craft_application.
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
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Grammar-aware project for *craft applications."""
from typing import Any

import pydantic
from craft_grammar.models import Grammar  # type: ignore[import-untyped]
from pydantic import ConfigDict

from craft_application.models.base import alias_generator
from craft_application.models.constraints import SingleEntryDict


class _GrammarAwareModel(pydantic.BaseModel):
    model_config = ConfigDict(
        validate_assignment=True,
        extra="allow",
        alias_generator=alias_generator,
        populate_by_name=True,
    )


class _GrammarAwarePart(_GrammarAwareModel):
    plugin: Grammar[str] | None = None
    source: Grammar[str] | None = None
    source_checksum: Grammar[str] | None = None
    source_branch: Grammar[str] | None = None
    source_commit: Grammar[str] | None = None
    source_depth: Grammar[int] | None = None
    source_subdir: Grammar[str] | None = None
    source_submodules: Grammar[list[str]] | None = None
    source_tag: Grammar[str] | None = None
    source_type: Grammar[str] | None = None
    disable_parallel: Grammar[bool] | None = None
    after: Grammar[list[str]] | None = None
    overlay_packages: Grammar[list[str]] | None = None
    stage_snaps: Grammar[list[str]] | None = None
    stage_packages: Grammar[list[str]] | None = None
    build_snaps: Grammar[list[str]] | None = None
    build_packages: Grammar[list[str]] | None = None
    build_environment: Grammar[list[SingleEntryDict[str, str]]] | None = None
    build_attributes: Grammar[list[str]] | None = None
    organize_files: Grammar[dict[str, str]] | None = pydantic.Field(
        default=None, alias="organize"
    )
    overlay_files: Grammar[list[str]] | None = pydantic.Field(None, alias="overlay")
    stage_files: Grammar[list[str]] | None = pydantic.Field(None, alias="stage")
    prime_files: Grammar[list[str]] | None = pydantic.Field(None, alias="prime")
    override_pull: Grammar[str] | None = None
    overlay_script: Grammar[str] | None = None
    override_build: Grammar[str] | None = None
    override_stage: Grammar[str] | None = None
    override_prime: Grammar[str] | None = None
    permissions: Grammar[list[dict[str, int | str]]] | None = None
    parse_info: Grammar[list[str]] | None = None


def get_grammar_aware_part_keywords() -> list[str]:
    """Return all supported grammar keywords for a part."""
    keywords: list[str] = [
        item.alias or name for name, item in _GrammarAwarePart.model_fields.items()
    ]
    return keywords


class GrammarAwareProject(_GrammarAwareModel):
    """Project definition containing grammar-aware components."""

    parts: "dict[str, _GrammarAwarePart]"

    @pydantic.model_validator(mode="before")
    @classmethod
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
        cls.model_validate(data)
