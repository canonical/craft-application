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
"""YAML helpers for craft applications."""
from collections.abc import Hashable
from typing import Any, Dict, Set, TextIO

import yaml


def _check_duplicate_keys(node: yaml.Node) -> None:
    """Ensure that the keys in a YAML node are not duplicates."""
    mappings: Set[yaml.Node] = set()

    for key_node, _ in node.value:
        try:
            if key_node.value in mappings:
                raise yaml.constructor.ConstructorError(
                    "while constructing a mapping",
                    node.start_mark,
                    f"found duplicate key {key_node.value!r}",
                    node.start_mark,
                )
            mappings.add(key_node.value)
        except TypeError:  # pragma: no cover
            # Ignore errors for malformed inputs that will be caught later.
            pass


def _dict_constructor(
    loader: yaml.Loader, node: yaml.MappingNode
) -> Dict[Hashable, Any]:
    _check_duplicate_keys(node)

    # Necessary in order to make yaml merge tags work
    loader.flatten_mapping(node)
    value = loader.construct_mapping(node)

    try:
        return dict(value)
    except TypeError as type_error:
        raise yaml.constructor.ConstructorError(
            "while constructing a mapping",
            node.start_mark,
            "found unhashable key",
            node.start_mark,
        ) from type_error


class _SafeYamlLoader(yaml.SafeLoader):
    def __init__(self, stream: TextIO) -> None:
        super().__init__(stream)

        self.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _dict_constructor
        )


def safe_yaml_load(stream: TextIO) -> Any:
    """Equivalent to pyyaml's safe_load function, but constraining duplicate keys.

    :param stream: Any text-like IO object.
    :returns: A dict object mapping the yaml.
    """
    # Silencing S506 ("probable use of unsafe loader") because we override it by using
    # our own safe loader.
    return yaml.load(stream, Loader=_SafeYamlLoader)  # noqa: S506
