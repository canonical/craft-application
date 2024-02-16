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
"""Unit tests for main Launchpad client."""
from __future__ import annotations

import enum
from unittest import mock

import pytest
from craft_application.launchpad import models


def flatten_enum(e: type[enum.Enum]) -> list:
    return [*e, *(val.name for val in e), *(val.value for val in e)]


def test_set_username_logged_in(fake_launchpad):
    assert fake_launchpad.username == "test_user"


def test_repr(fake_launchpad):
    assert repr(fake_launchpad) == "Launchpad('testcraft')"


@pytest.mark.parametrize("type_", flatten_enum(models.RecipeType))
def test_get_recipe_finds_type(monkeypatch, fake_launchpad, type_):
    monkeypatch.setattr(models.SnapRecipe, "get", mock.Mock())
    monkeypatch.setattr(models.CharmRecipe, "get", mock.Mock())

    fake_launchpad.get_recipe(type_, "my_recipe", "test_user", "my_project")


def test_get_recipe_sets_owner(fake_launchpad):
    with mock.patch("craft_application.launchpad.models.SnapRecipe.get") as mock_get:
        assert fake_launchpad.get_recipe("snap", "my_recipe") == mock_get.return_value
    mock_get.assert_called_once_with(fake_launchpad, "my_recipe", "test_user")


@pytest.mark.parametrize("type_", ["snap", "Snap", "SNAP", models.RecipeType.SNAP])
@pytest.mark.parametrize("owner", [None, "test_user", "someone_else"])
def test_get_recipe_snap(fake_launchpad, type_, owner):
    with mock.patch("craft_application.launchpad.models.SnapRecipe.get") as mock_get:
        assert (
            fake_launchpad.get_recipe(type_, "my_recipe", owner)
            == mock_get.return_value
        )

    mock_get.assert_called_once_with(
        fake_launchpad, "my_recipe", owner or fake_launchpad.username
    )


@pytest.mark.parametrize("type_", ["charm", "Charm", models.RecipeType.CHARM])
def test_get_recipe_charm(fake_launchpad, type_):
    with mock.patch("craft_application.launchpad.models.CharmRecipe.get") as mock_get:
        assert (
            fake_launchpad.get_recipe(type_, "my_recipe", project="my_project")
            == mock_get.return_value
        )

    mock_get.assert_called_once_with(
        fake_launchpad, "my_recipe", "test_user", "my_project"
    )


def test_get_recipe_charm_has_project(fake_launchpad):
    with pytest.raises(
        ValueError, match="A charm recipe must be associated with a project."
    ):
        fake_launchpad.get_recipe(models.RecipeType.CHARM, "my_recipe")
