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

from typing import Any

from craft_grammar import GrammarProcessor  # type: ignore[import-untyped]

_KEYS = [
    "source",
    "build-environment",
    "build-packages",
    "stage-packages",
    "build-snaps",
    "stage-snaps",
]

_SCALAR_VALUES = ["source"]


def process_part(
    *, part_yaml_data: dict[str, Any], processor: GrammarProcessor
) -> dict[str, Any]:
    """Process grammar for a given part."""
    existing_keys = (key for key in _KEYS if key in part_yaml_data)

    for key in existing_keys:
        unprocessed_grammar = part_yaml_data[key]

        if key in _SCALAR_VALUES and isinstance(unprocessed_grammar, str):
            unprocessed_grammar = [unprocessed_grammar]

        processed_grammar = processor.process(grammar=unprocessed_grammar)

        if key in _SCALAR_VALUES:
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
