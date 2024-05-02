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

"""Grammar-aware craft-parts Part."""

import pydantic
from craft_grammar.models import Grammar

from ._base import _GrammarAwareModel


class _GrammarAwarePart(_GrammarAwareModel):
    plugin: Grammar[str] | None
    source: Grammar[str] | None
    source_checksum: Grammar[str] | None
    source_branch: Grammar[str] | None
    source_commit: Grammar[str] | None
    source_depth: Grammar[int] | None
    source_subdir: Grammar[str] | None
    source_submodules: Grammar[list[str]] | None
    source_tag: Grammar[str] | None
    source_type: Grammar[str] | None
    disable_parallel: Grammar[bool] | None
    after: Grammar[list[str]] | None
    overlay_packages: Grammar[list[str]] | None
    stage_snaps: Grammar[list[str]] | None
    stage_packages: Grammar[list[str]] | None
    build_snaps: Grammar[list[str]] | None
    build_packages: Grammar[list[str]] | None
    build_environment: (
        Grammar[list[dict]] | None  # pyright: ignore[reportMissingTypeArgument]
    )
    build_attributes: Grammar[list[str]] | None
    organize_files: Grammar[dict[str, str]] | None = pydantic.Field(alias="organize")
    overlay_files: Grammar[list[str]] | None = pydantic.Field(alias="overlay")
    stage_files: Grammar[list[str]] | None = pydantic.Field(alias="stage")
    prime_files: Grammar[list[str]] | None = pydantic.Field(alias="prime")
    override_pull: Grammar[str] | None
    overlay_script: Grammar[str] | None
    override_build: Grammar[str] | None
    override_stage: Grammar[str] | None
    override_prime: Grammar[str] | None
    permissions: (
        Grammar[list[dict]] | None  # pyright: ignore[reportMissingTypeArgument]
    )
    parse_info: Grammar[list[str]] | None


def get_grammar_aware_part_keywords() -> list[str]:
    """Return all supported grammar keywords for a part."""
    keywords: list[str] = [item.alias for item in _GrammarAwarePart.__fields__.values()]
    return keywords
