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

import itertools
from typing import Any, cast

import craft_cli
from craft_grammar import GrammarProcessor, Variant  # type: ignore[import-untyped]
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
    for key, part_data in part_yaml_data.items():
        unprocessed_grammar = part_data

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
                    not isinstance(key, str)
                    for key in item  # type: ignore[reportUnknownVariableType]
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

        part_yaml_data[key] = post_process_grammar(
            processor, key, processed_grammar, part_yaml_data
        )

    return part_yaml_data


def post_process_grammar(
    processor: GrammarProcessor,
    key: str,
    processed_grammar: list[Any],
    part_yaml_data: dict[str, Any],
) -> list[Any] | dict[str, str] | None:
    """Post-process primitives returned by the grammar processor.

    Special cases:
    - Scalar values should be returned as a single object instead of a list.
    - Dict values should be returned as a dict instead of a list.

    :returns: the post-processed primitives
    """
    if processor.variant == Variant.FOR_VARIANT:
        if key in _DICT_ONLY_VALUES:
            return merge_processed_dict(processed_grammar, part_yaml_data)
        if key not in _NON_SCALAR_VALUES:
            return processed_grammar[0] if processed_grammar else None
    elif key not in _NON_SCALAR_VALUES or key in _DICT_ONLY_VALUES:
        return processed_grammar[0] if processed_grammar else None
    return processed_grammar


def merge_processed_dict(
    processed_grammar: list[Any],
    part_yaml_data: dict[str, Any],
) -> dict[str, str] | None:
    """Merge list of dicts in a single dict.

    :raises: CraftValidationError if duplicate keys are found.
    :returns: Merged dict.
    """
    processed_grammar_dict: dict[str, str] = {}
    processed_grammar_sets: list[set[str]] = []
    all_duplicates: list[str] = []

    if not processed_grammar:
        return None

    for d in processed_grammar:
        processed_grammar_sets.append(d.keys())
        processed_grammar_dict.update(d)

    # Look for duplicates
    for a, b in itertools.combinations(processed_grammar_sets, 2):
        duplicates = a & b
        if duplicates:
            all_duplicates.extend(duplicates)

    if all_duplicates:
        raise CraftValidationError(
            f"Duplicate keys in processed dict {all_duplicates} in '{part_yaml_data}'"
        )

    return processed_grammar_dict


def process_parts(
    *,
    parts_yaml_data: dict[str, Any],
    arch: str,
    target_arch: str,
    platform_ids: set[str],
) -> dict[str, Any]:
    """Process grammar for parts.

    :param yaml_data: The parts data with grammar to process. Grammar is
        processed in-place in this dictionary.
    :param arch: The architecture the system is on. This is used as the
        selector for the 'on' statement.
    :param target_arch: The architecture the system is to build for. This
        is the selector for the 'to' statement.
    :param platform_ids: The identifiers for the current platform to build.
        These are the selectors for the 'for' statement.

    :returns: The processed parts data.
    """

    def self_check(value: Any) -> bool:  # noqa: ANN401
        return bool(
            value == value  # pylint: disable=comparison-with-itself  # noqa: PLR0124
        )

    # TODO: make checker optional in craft-grammar.  # noqa: FIX002
    processor = GrammarProcessor(
        arch=arch,
        target_arch=target_arch,
        platforms=platform_ids,
        checker=self_check,
    )

    for part_name, part_data in parts_yaml_data.items():
        parts_yaml_data[part_name] = process_part(
            part_yaml_data=part_data, processor=processor
        )

    return parts_yaml_data
