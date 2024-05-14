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
"""Grammar processor."""

from typing import Any, cast

import craft_cli
from craft_grammar import GrammarProcessor  # type: ignore[import-untyped]
from craft_grammar.errors import GrammarSyntaxError  # type: ignore[import-untyped]

from craft_application.errors import CraftValidationError
from craft_application.models import get_grammar_aware_part_keywords

# Values that should return as a single object / list / dict.
_NON_SCALAR_VALUES = [
    "source-submodules",
    "after",
    "overlay-packages",
    "build-attributes",
    "permissions",
    "build-environment",
    "build-packages",
    "stage-packages",
    "build-snaps",
    "stage-snaps",
    "overlay",
    "organize",
    "stage",
    "prime",
]

# Values that should return a dict, not in a list.
_DICT_ONLY_VALUES = [
    "organize",
]


def process_part(
    *, part_yaml_data: dict[str, Any], processor: GrammarProcessor
) -> dict[str, Any]:
    """Process grammar for a given part."""
    for key in part_yaml_data:
        unprocessed_grammar = part_yaml_data[key]

        # ignore non-grammar keywords
        if key not in get_grammar_aware_part_keywords():
            craft_cli.emit.debug(
                f"Not processing grammar for non-grammar enabled keyword {key}"
            )
            continue

        craft_cli.emit.debug(f"Processing grammar for {key}: {unprocessed_grammar}")
        # grammar aware models can be strings or list of dicts and strings
        if isinstance(unprocessed_grammar, list):
            # all items in the list must be a dict or a string
            if any(not isinstance(d, dict | str) for d in unprocessed_grammar):  # type: ignore[reportUnknownVariableType]
                continue

            # all keys in the dictionary must be a string
            for item in unprocessed_grammar:  # type: ignore[reportUnknownVariableType]
                if isinstance(item, dict) and any(
                    not isinstance(key, str) for key in item  # type: ignore[reportUnknownVariableType]
                ):
                    continue

            unprocessed_grammar = cast(list[dict[str, Any] | str], unprocessed_grammar)
        # grammar aware models can be a string
        elif isinstance(unprocessed_grammar, str):
            unprocessed_grammar = [unprocessed_grammar]
        # skip all other data types
        else:
            continue

        try:
            processed_grammar = processor.process(grammar=unprocessed_grammar)
        except GrammarSyntaxError as e:
            raise CraftValidationError(
                f"Invalid grammar syntax while processing '{key}' in '{part_yaml_data}': {e}"
            ) from e

        # special cases:
        # - scalar values should return as a single object, not in a list.
        # - dict values should return as a dict, not in a list.
        if key not in _NON_SCALAR_VALUES or key in _DICT_ONLY_VALUES:
            processed_grammar = processed_grammar[0] if processed_grammar else None

        part_yaml_data[key] = processed_grammar

    return part_yaml_data


def process_parts(
    *, parts_yaml_data: dict[str, Any], arch: str, target_arch: str
) -> dict[str, Any]:
    """Process grammar for parts.

    :param yaml_data: unprocessed snapcraft.yaml.
    :returns: process snapcraft.yaml.
    """

    def self_check(value: Any) -> bool:  # noqa: ANN401
        return bool(
            value == value  # pylint: disable=comparison-with-itself  # noqa: PLR0124
        )

    # TODO: make checker optional in craft-grammar.
    processor = GrammarProcessor(arch=arch, target_arch=target_arch, checker=self_check)

    for part_name in parts_yaml_data:
        parts_yaml_data[part_name] = process_part(
            part_yaml_data=parts_yaml_data[part_name], processor=processor
        )

    return parts_yaml_data
