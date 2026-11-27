# This file is part of craft_application.
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
"""Witchcraft extensions."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from craft_application.extensions import Extension
from typing_extensions import override

if TYPE_CHECKING:
    from collections.abc import Sequence


class PotionExtension(Extension):
    """Extension for brewing potions."""

    name = "potion"

    @staticmethod
    @override
    def get_supported_bases() -> Sequence[str]:
        return ("ubuntu@22.04", "ubuntu@24.04")

    @staticmethod
    @override
    def is_experimental(base: str | None) -> bool:
        return False

    @override
    def get_root_snippet(self) -> dict[str, Any]:
        return {"title": "Potion Cauldron (mystic)"}

    @override
    def get_parts_snippet(self) -> dict[str, Any]:
        return {
            f"{self.extension_name}/brewing": {
                "plugin": "nil",
                "stage-packages": ["belladonna"],
            }
        }
