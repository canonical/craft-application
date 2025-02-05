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
"""Unit tests for launchpad recipe models."""
from unittest import mock

import pytest

from craft_application.launchpad import CharmRecipe, RecipeType, RockRecipe, SnapRecipe
from craft_application.launchpad.models import get_recipe_class
from craft_application.launchpad.models.recipe import BaseRecipe


def test_get_recipe_class():
    assert get_recipe_class(RecipeType.SNAP) is SnapRecipe
    assert get_recipe_class(RecipeType.CHARM) is CharmRecipe
    assert get_recipe_class(RecipeType.ROCK) is RockRecipe


def test_get_recipe_class_invalid():
    with pytest.raises(TypeError):
        get_recipe_class("invalid")  # pyright: ignore[reportArgumentType]


@pytest.mark.parametrize("recipe_type", list(RecipeType.__members__.values()))
def test_get_recipe_class_exhaustive(recipe_type):
    obtained = get_recipe_class(recipe_type)
    assert issubclass(obtained, BaseRecipe)


def test_standard_recipe_architectures():
    with pytest.raises(ValueError, match="charm recipes do not support architectures"):
        CharmRecipe.new(
            lp=mock.Mock(),
            name="recipe",
            owner="owner",
            project="project",
            architectures=["amd64"],
        )
