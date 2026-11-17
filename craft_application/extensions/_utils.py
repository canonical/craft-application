# This file is part of craft-application.
#
# Copyright 2026 Canonical Ltd.
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
"""Extension processing utilities."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING, Any

from craft_application import errors
from craft_application.extensions.registry import get_extension_class

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path

    from craft_application.extensions.extension import Extension
    from craft_application.services import ServiceFactory


def apply_extensions(
    project_root: Path,
    yaml_data: dict[str, Any],
    *,
    extensions: Sequence[str],
    app_name: str,
    build_for: str | None = None,
    services: ServiceFactory | None = None,
) -> dict[str, Any]:
    """Apply declared extensions to the project YAML data in-place.

    Extensions are applied in the order declared.
    """
    for extension_name in extensions:
        if not isinstance(extension_name, str):
            raise errors.ExtensionError(
                f"Extension name {extension_name!r} must be a string.",
                resolution="Ensure all entries in 'extensions' are strings.",
            )

        extension_class = get_extension_class(extension_name)
        extension = extension_class(
            project_root=project_root,
            yaml_data=copy.deepcopy(yaml_data),
            app_name=app_name,
            build_for=build_for,
            services=services,
        )
        extension.validate()
        _apply_extension(yaml_data, extension)

    return yaml_data


def _apply_extension(yaml_data: dict[str, Any], extension: Extension) -> None:
    """Apply a single extension to the project YAML data."""
    root_extension = extension.get_root_snippet()
    for property_name, property_value in root_extension.items():
        yaml_data[property_name] = _apply_extension_property(
            yaml_data.get(property_name), property_value
        )

    parts = yaml_data.setdefault("parts", {})
    for part_name, part_definition in list(parts.items()):
        if not isinstance(part_definition, dict):
            continue
        part_extension = extension.get_part_snippet(
            part_name=part_name,
            plugin_name=part_definition.get("plugin"),
        )
        for property_name, property_value in part_extension.items():
            part_definition[property_name] = _apply_extension_property(
                part_definition.get(property_name), property_value
            )

    parts_snippet = extension.get_parts_snippet()
    for part_name, part_definition in parts_snippet.items():
        if part_name not in parts:
            parts[part_name] = part_definition


def _apply_extension_property(
    existing_property: Any,  # noqa: ANN401
    extension_property: Any,  # noqa: ANN401
) -> Any:  # noqa: ANN401
    """Recursively merge an extension snippet property with an existing property."""
    if existing_property is not None:
        if isinstance(existing_property, list) and isinstance(extension_property, list):
            merged = extension_property + existing_property
            if all(isinstance(item, str) for item in merged):
                return _remove_list_duplicates(merged)
            return merged

        if isinstance(existing_property, dict) and isinstance(extension_property, dict):
            for key, value in extension_property.items():
                existing_property[key] = _apply_extension_property(
                    existing_property.get(key), value
                )
            return existing_property

        return existing_property

    return extension_property


def _remove_list_duplicates(seq: list[str]) -> list[str]:
    """Remove duplicates from a list of strings while preserving order."""
    seen: set[str] = set()
    deduped: list[str] = []
    for item in seq:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped
