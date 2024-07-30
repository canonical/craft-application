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
from craft_grammar.models import (  # type: ignore[import-untyped]
    GrammarBool,
    GrammarDict,
    GrammarDictList,
    GrammarInt,
    GrammarSingleEntryDictList,
    GrammarStr,
    GrammarStrList,
)

from craft_application.models.base import alias_generator
from pydantic import ConfigDict


class _GrammarAwareModel(pydantic.BaseModel):
    model_config = ConfigDict(validate_assignment=True, extra=pydantic.Extra.allow, alias_generator=alias_generator, populate_by_name=True)


class _GrammarAwarePart(_GrammarAwareModel):
    plugin: GrammarStr | None = None
    source: GrammarStr | None = None
    source_checksum: GrammarStr | None = None
    source_branch: GrammarStr | None = None
    source_commit: GrammarStr | None = None
    source_depth: GrammarInt | None = None
    source_subdir: GrammarStr | None = None
    source_submodules: GrammarStrList | None = None
    source_tag: GrammarStr | None = None
    source_type: GrammarStr | None = None
    disable_parallel: GrammarBool | None = None
    after: GrammarStrList | None = None
    overlay_packages: GrammarStrList | None = None
    stage_snaps: GrammarStrList | None = None
    stage_packages: GrammarStrList | None = None
    build_snaps: GrammarStrList | None = None
    build_packages: GrammarStrList | None = None
    build_environment: GrammarSingleEntryDictList | None = None
    build_attributes: GrammarStrList | None = None
    organize_files: GrammarDict | None = pydantic.Field(alias="organize")
    overlay_files: GrammarStrList | None = pydantic.Field(alias="overlay")
    stage_files: GrammarStrList | None = pydantic.Field(alias="stage")
    prime_files: GrammarStrList | None = pydantic.Field(alias="prime")
    override_pull: GrammarStr | None = None
    overlay_script: GrammarStr | None = None
    override_build: GrammarStr | None = None
    override_stage: GrammarStr | None = None
    override_prime: GrammarStr | None = None
    permissions: GrammarDictList | None = None
    parse_info: GrammarStrList | None = None


def get_grammar_aware_part_keywords() -> list[str]:
    """Return all supported grammar keywords for a part."""
    keywords: list[str] = [item.alias for item in _GrammarAwarePart.__fields__.values()]
    return keywords


class GrammarAwareProject(_GrammarAwareModel):
    """Project definition containing grammar-aware components."""

    parts: "dict[str, _GrammarAwarePart]"

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
