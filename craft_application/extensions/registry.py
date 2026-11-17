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
"""Extension registry."""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING, Any, cast

from craft_application import errors

if TYPE_CHECKING:
    from craft_application.extensions.extension import Extension


class ExtensionRegistry:
    """Registry for lazy-loading extension classes."""

    _extension_classes: dict[str, tuple[str, str] | type[Extension]] = {}

    @classmethod
    def register(
        cls,
        name: str,
        extension_class: type[Extension] | str,
        *,
        module: str | None = None,
    ) -> None:
        """Register an extension class.

        :param name: the name of the extension.
        :param extension_class: either an Extension class or string naming the class.
        :param module: module from which to import the class if passed as string.
        """
        if isinstance(extension_class, str):
            if module is None:
                raise KeyError("Must set module if extension_class is set by name.")
            cls._extension_classes[name] = (module, extension_class)
        else:
            if module is not None:
                raise KeyError(
                    "Must not set module if extension_class is passed by value."
                )
            cls._extension_classes[name] = extension_class

    @classmethod
    def unregister(cls, name: str) -> None:
        """Unregister an extension by name."""
        del cls._extension_classes[name]

    @classmethod
    def reset(cls) -> None:
        """Clear all registered extensions."""
        cls._extension_classes.clear()

    @classmethod
    def get_extension_class(cls, name: str) -> type[Extension]:
        """Obtain an extension class given its name, importing lazily if needed."""
        if name not in cls._extension_classes:
            names = ", ".join(repr(n) for n in sorted(cls._extension_classes.keys()))
            raise errors.ExtensionError(
                f"Extension {name!r} does not exist.",
                resolution=f"Available extensions: {names}"
                if names
                else "No extensions registered.",
            )

        entry = cls._extension_classes[name]
        if isinstance(entry, tuple):
            module_name, class_name = entry
            mod = importlib.import_module(module_name)
            return cast(type["Extension"], getattr(mod, class_name))
        return entry

    @classmethod
    def get_extension_names(cls) -> list[str]:
        """Obtain the list of registered extension names."""
        return sorted(cls._extension_classes.keys())

    @classmethod
    def get_extensions_metadata(cls) -> list[dict[str, Any]]:
        """Return metadata for all registered extensions."""
        metadata: list[dict[str, Any]] = []
        for name in cls.get_extension_names():
            ext_cls = cls.get_extension_class(name)
            metadata.append(
                {
                    "name": name,
                    "bases": sorted(ext_cls.get_supported_bases()),
                    "experimental": ext_cls.is_experimental(None),
                }
            )
        return metadata


register = ExtensionRegistry.register
unregister = ExtensionRegistry.unregister
reset = ExtensionRegistry.reset
get_extension_class = ExtensionRegistry.get_extension_class
get_extension_names = ExtensionRegistry.get_extension_names
get_extensions = ExtensionRegistry.get_extensions_metadata
