#  This file is part of craft-application.
#
#  Copyright 2024 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Launchpad client.

This module is self-contained as it could be moved into its own package.
"""

from . import errors
from .errors import LaunchpadError
from .launchpad import Launchpad
from .models import LaunchpadObject, RecipeType, Recipe, SnapRecipe, CharmRecipe
from .util import Architecture

__all__ = [
    "errors",
    "LaunchpadError",
    "Launchpad",
    "LaunchpadObject",
    "RecipeType",
    "Recipe",
    "SnapRecipe",
    "CharmRecipe",
    "Architecture",
]
