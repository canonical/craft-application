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

from collections.abc import Sequence
from typing import Any, cast

import craft_cli
from craft_grammar import GrammarProcessor  # type: ignore[import-untyped]
from craft_grammar.errors import GrammarSyntaxError  # type: ignore[import-untyped]

from craft_application.errors import CraftValidationError
from craft_application.models import (
    get_grammar_aware_part_keywords,
    get_grammar_aware_repository_keywords,
)

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


def process_project(*, yaml_data: dict[str, Any], arch: str, target_arch: str) -> None:
    """Process grammar for project data."""
    if "parts" in yaml_data:
        process_parts(
            parts_yaml_data=yaml_data["parts"], arch=arch, target_arch=target_arch
        )

    if "package-repositories" in yaml_data:
        process_repositories(
            repo_yaml_data=yaml_data["package-repositories"],
            arch=arch,
            target_arch=target_arch,
        )


def process_part(
    *, part_yaml_data: dict[str, Any], processor: GrammarProcessor
) -> dict[str, Any]:
    """Process grammar for a given part."""
    return _process_dict(
        yaml_data=part_yaml_data,
        processor=processor,
        grammar_keywords=get_grammar_aware_part_keywords(),
        non_scalar=_NON_SCALAR_VALUES,
        dict_only=_DICT_ONLY_VALUES,
    )


def process_parts(
    *, parts_yaml_data: dict[str, Any], arch: str, target_arch: str
) -> dict[str, Any]:
    """Process grammar for parts.

    :param yaml_data: unprocessed snapcraft.yaml.
    :returns: process snapcraft.yaml.
    """
    processor = GrammarProcessor(
        arch=arch, target_arch=target_arch, checker=_self_check
    )

    for part_name in parts_yaml_data:
        parts_yaml_data[part_name] = process_part(
            part_yaml_data=parts_yaml_data[part_name], processor=processor
        )

    return parts_yaml_data


def process_repository(
    *, repo_data: dict[str, Any], processor: GrammarProcessor
) -> None:
    """Process grammar for a given package-repository."""
    repo_grammar_keywords = get_grammar_aware_repository_keywords()
    non_scalar = ["architectures", "components", "formats", "suites"]
    dict_only: list[str] = []
    _process_dict(
        yaml_data=repo_data,
        processor=processor,
        grammar_keywords=repo_grammar_keywords,
        non_scalar=non_scalar,
        dict_only=dict_only,
    )


def process_repositories(
    *, repo_yaml_data: list[dict[str, Any]], arch: str, target_arch: str
) -> None:
    """Process grammar for all package-repositories on a project."""
    processor = GrammarProcessor(
        arch=arch, target_arch=target_arch, checker=_self_check
    )
    for repo_data in repo_yaml_data:
        process_repository(repo_data=repo_data, processor=processor)


def _process_dict(
    *,
    yaml_data: dict[str, Any],
    processor: GrammarProcessor,
    grammar_keywords: Sequence[str],
    non_scalar: Sequence[str],
    dict_only: Sequence[str],
) -> dict[str, Any]:
    """Process the grammar for all fields in ``yaml_data``.

    :param yaml_data: dict representing a model object.
    :param processor: the processor to use.
    :param grammar_keywords: the set of keys in that are grammar-aware.
    :param non_scalar: the set of keys whose values are expected to be sequences
      after grammar is processed.
    :param dict_only: the set of keys whose values are expected to be dicts
      after grammar is processed.
    """
    for key in yaml_data:
        unprocessed_grammar = yaml_data[key]

        # ignore non-grammar keywords
        if key not in grammar_keywords:
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
                f"Invalid grammar syntax while processing '{key}' in '{yaml_data}': {e}"
            ) from e

        # special cases:
        # - scalar values should return as a single object, not in a list.
        # - dict values should return as a dict, not in a list.
        if key not in non_scalar or key in dict_only:
            processed_grammar = processed_grammar[0] if processed_grammar else None

        yaml_data[key] = processed_grammar

    return yaml_data


def _self_check(value: Any) -> bool:  # noqa: ANN401
    return bool(value == value)  # noqa: PLR0124
