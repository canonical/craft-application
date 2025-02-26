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

from __future__ import annotations

import contextlib
import pathlib
from typing import TYPE_CHECKING, Any, TextIO, cast, overload

import yaml
from yaml.composer import Composer
from yaml.constructor import Constructor
from yaml.nodes import MappingNode, Node, ScalarNode
from yaml.resolver import BaseResolver

from craft_application import errors

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Hashable


# pyright: reportUnknownMemberType=false
# Type of "represent_scalar" is
# (tag: str, value: Unknown, style: str | None = None) -> ScalarNode
def _repr_str(dumper: yaml.Dumper, data: str) -> yaml.ScalarNode:
    """Multi-line string representer for the YAML dumper."""
    if "\n" in data:
        return dumper.represent_scalar("tag:yaml.org,2002:str", data, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", data)


def _check_duplicate_key_node(
    mappings: set[yaml.Node], key: yaml.Node, node: yaml.Node
) -> None:
    """Check for duplicate key nodes within a mapping."""
    if key in mappings:
        raise yaml.constructor.ConstructorError(
            "while constructing a mapping",
            node.start_mark,
            f"found duplicate key {key!r}",
            node.start_mark,
        )
    mappings.add(key)


def _check_duplicate_keys(node: yaml.Node) -> None:
    """Ensure that the keys in a YAML node are not duplicates."""
    mappings: set[yaml.Node] = set()

    for key_node, _ in node.value:
        with contextlib.suppress(TypeError):
            _check_duplicate_key_node(mappings, key_node.value, node)


def _dict_constructor(
    loader: yaml.Loader, node: yaml.MappingNode
) -> dict[Hashable, Any]:
    _check_duplicate_keys(node)

    # Necessary in order to make yaml merge tags work
    loader.flatten_mapping(node)
    value = loader.construct_mapping(node)

    try:
        return dict(value)
    # This `except` clause may be unnecessary as an earlier constructor appears
    # to raise this issue before the dict constructor gets to it, but I'm not
    # comfortable enough with the internals of PyYAML to say for sure.
    # As such, I'm marking it with no cover for right now and have created
    # https://github.com/canonical/craft-application/issues/24
    # to see if someone else knows better. (This code came from snapcraft initially.)
    except TypeError as type_error:  # pragma: no cover
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


class _SafeLineNoLoader(_SafeYamlLoader):
    def __init__(self, stream: TextIO) -> None:
        super().__init__(stream)

        self.add_constructor(
            yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _dict_constructor
        )

    def compose_node(self, parent: Node | None, index: int) -> Node:
        # the line number where the previous token has ended (plus empty lines)
        line = self.line
        node = Composer.compose_node(self, parent, index)
        node.__line__ = line + 1
        return node

    def construct_mapping(
        self,
        node: MappingNode,
        deep: bool = False,  # noqa: FBT001, FBT002 - used internally by yaml.SafeLoader
    ) -> dict[Hashable, Any]:
        node_pair_lst = node.value
        node_pair_lst_for_appending = []

        for key_node, _ in node_pair_lst:
            shadow_key_node = ScalarNode(
                tag=BaseResolver.DEFAULT_SCALAR_TAG, value="__line__" + key_node.value
            )
            shadow_value_node = ScalarNode(
                tag=BaseResolver.DEFAULT_SCALAR_TAG, value=key_node.__line__
            )
            node_pair_lst_for_appending.append((shadow_key_node, shadow_value_node))

        node.value = node_pair_lst + node_pair_lst_for_appending
        return Constructor.construct_mapping(self, node, deep=deep)


def safe_yaml_load(stream: TextIO) -> Any:  # noqa: ANN401 - The YAML could be anything
    """Equivalent to pyyaml's safe_load function, but constraining duplicate keys.

    :param stream: Any text-like IO object.
    :returns: A dict object mapping the yaml.
    """
    try:
        # Silencing S506 ("probable use of unsafe loader") because we override it by
        # using our own safe loader.
        return yaml.load(stream, Loader=_SafeYamlLoader)  # noqa: S506
    except yaml.YAMLError as error:
        filename = pathlib.Path(stream.name).name
        raise errors.YamlError.from_yaml_error(filename, error) from error


def safe_yaml_load_with_lines(stream: TextIO) -> Any:  # noqa: ANN401 - The YAML could be anything
    """Equivalent to pyyaml's safe_load function, but constraining duplicate keys and including line numbers.

    :param stream: Any text-like IO object.
    :returns: A dict object mapping the yaml.
    """
    try:
        # Silencing S506 ("probable use of unsafe loader") because we override it by
        # using our own safe loader.
        return yaml.load(stream, Loader=_SafeLineNoLoader)  # noqa: S506
    except yaml.YAMLError as error:
        filename = pathlib.Path(stream.name).name
        raise errors.YamlError.from_yaml_error(filename, error) from error


@overload
def dump_yaml(
    data: Any,  # noqa: ANN401 # Any gets passed to pyyaml
    stream: TextIO,
    **kwargs: Any,
) -> None: ...  # pragma: no cover


@overload
def dump_yaml(
    data: Any,  # noqa: ANN401 # Any gets passed to pyyaml
    stream: None = None,
    **kwargs: Any,
) -> str: ...  # pragma: no cover


def dump_yaml(data: Any, stream: TextIO | None = None, **kwargs: Any) -> str | None:
    """Dump an object to YAML using PyYAML.

    This works as a drop-in replacement for ``yaml.safe_dump``, but adjusting
    formatting as appropriate.

    :param data: the data structure to dump.
    :param stream: The optional text stream to which to write.
    :param kwargs: Keyword arguments passed to pyyaml
    """
    yaml.add_representer(
        str, _repr_str, Dumper=cast(type[yaml.Dumper], yaml.SafeDumper)
    )
    kwargs.setdefault("sort_keys", False)
    kwargs.setdefault("allow_unicode", True)
    return cast(  # This cast is needed for pyright but not mypy
        str | None, yaml.dump(data, stream, Dumper=yaml.SafeDumper, **kwargs)
    )


def flatten_yaml_data(data: dict[str, Any]) -> dict[str, Any]:
    """Recursively flattens a nested dictionary by removing the '__line__' fields."""
    if type(data) is not dict:
        return data
    return {k: flatten_yaml_data(v) for k, v in data.items() if "__line__" not in k}
