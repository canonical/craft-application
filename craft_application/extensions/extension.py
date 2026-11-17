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
"""Extension base class definition."""

from __future__ import annotations

import abc
import os
from typing import TYPE_CHECKING, Any, ClassVar

from craft_cli import emit

from craft_application import errors

if TYPE_CHECKING:
    from collections.abc import Sequence
    from pathlib import Path


class Extension(abc.ABC):
    """Base class from which all extensions inherit.

    Extensions can add snippets to the project root, modify parts, and inject new parts.
    """

    name: ClassVar[str]

    def __init__(
        self,
        *,
        project_root: Path,
        yaml_data: dict[str, Any],
        app_name: str,
        build_for: str | None = None,
    ) -> None:
        self.project_root = project_root
        self.yaml_data = yaml_data
        self.app_name = app_name
        self.build_for = build_for

    @property
    def extension_name(self) -> str:
        """Return the name of this extension."""
        return self.name

    @staticmethod
    @abc.abstractmethod
    def get_supported_bases() -> Sequence[str]:
        """Return supported bases for this extension."""

    @staticmethod
    @abc.abstractmethod
    def is_experimental(base: str | None) -> bool:
        """Return whether this extension is experimental for the given base."""

    def get_root_snippet(self) -> dict[str, Any]:
        """Return the root snippet to apply to the project."""
        return {}

    def get_part_snippet(
        self,
        *,
        part_name: str | None = None,  # noqa: ARG002
        plugin_name: str | None = None,  # noqa: ARG002
        **kwargs: Any,  # noqa: ARG002
    ) -> dict[str, Any]:
        """Return snippet to apply to existing parts."""
        return {}

    def get_parts_snippet(self) -> dict[str, Any]:
        """Return new parts to add to the project."""
        return {}

    def validate(self) -> None:
        """Validate that the extension is compatible with the current project."""
        base: str | None = self.yaml_data.get("build-base") or self.yaml_data.get(
            "base"
        )
        if base:
            if self.is_experimental(base):
                app_env = f"{self.app_name.upper()}_ENABLE_EXPERIMENTAL_EXTENSIONS"
                if not os.getenv(app_env) and not os.getenv(
                    "CRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS"
                ):
                    raise errors.ExtensionError(
                        f"Extension {self.name!r} is experimental on base {base!r}.",
                        resolution=f"Set {app_env}=1 to enable experimental extensions.",
                    )
                emit.progress(
                    f"*EXPERIMENTAL* extension {self.name!r} enabled",
                    permanent=True,
                )

            supported_bases = self.get_supported_bases()
            if supported_bases and base not in supported_bases:
                supported_str = ", ".join(sorted(supported_bases))
                raise errors.ExtensionError(
                    f"Extension {self.name!r} does not support base {base!r}.",
                    resolution=f"Supported bases are: {supported_str}.",
                )

        invalid_parts = [
            p
            for p in self.get_parts_snippet()
            if not p.startswith(f"{self.name}/") and not p.startswith(f"{self.name}.")
        ]
        if invalid_parts:
            raise errors.ExtensionError(
                f"Extension {self.name!r} defines invalid part names: {invalid_parts!r}.",
                resolution=f"Prefix extension part names with '{self.name}/'.",
            )
