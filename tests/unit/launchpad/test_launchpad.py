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
import pathlib
from unittest import mock

import launchpadlib.launchpad
import launchpadlib.uris
import pytest
from craft_application import launchpad
from craft_application.launchpad import models


def flatten_enum(e: type[enum.Enum]) -> list:
    return [*e, *(val.name for val in e), *(val.value for val in e)]


@pytest.mark.parametrize(
    "cache_path",
    [
        launchpad.launchpad.DEFAULT_CACHE_PATH,
        "/cache",
        "some/cache/directory",
    ],
)
@pytest.mark.parametrize(
    "root", [launchpadlib.uris.LPNET_SERVICE_ROOT, "production", "staging"]
)
@pytest.mark.usefixtures("fs")  # Fake filesystem
def test_anonymous_login_with_cache(mocker, cache_path, root):
    # Workaround for Python 3.10's interaction with pyfakefs.
    cache_path = pathlib.Path(str(cache_path))

    assert not cache_path.exists()
    mock_login = mocker.patch.object(
        launchpadlib.launchpad.Launchpad, "login_anonymously"
    )
    launchpad.Launchpad.anonymous(
        "craft-application-tests", cache_dir=cache_path, root=root
    )

    assert cache_path.exists()
    mock_login.assert_called_once_with(
        consumer_name="craft-application-tests",
        service_root=root,
        launchpadlib_dir=cache_path.expanduser().resolve(),
        version="devel",
        timeout=None,
    )


@pytest.mark.usefixtures("fs")
def test_anonymous_login_no_cache(mocker):
    mock_login = mocker.patch.object(
        launchpadlib.launchpad.Launchpad, "login_anonymously"
    )

    launchpad.Launchpad.anonymous("craft-application-tests", cache_dir=None)

    mock_login.assert_called_once_with(
        consumer_name="craft-application-tests",
        service_root=launchpadlib.uris.LPNET_SERVICE_ROOT,
        launchpadlib_dir=None,
        version="devel",
        timeout=None,
    )


@pytest.mark.parametrize(
    "cache_path",
    [
        launchpad.launchpad.DEFAULT_CACHE_PATH,
        pathlib.Path("/cache"),
        pathlib.Path("some/cache/directory"),
    ],
)
@pytest.mark.parametrize(
    "root", [launchpadlib.uris.LPNET_SERVICE_ROOT, "production", "staging"]
)
@pytest.mark.parametrize(
    "credentials_file",
    [
        pathlib.Path("/creds"),
        pathlib.Path("some/credentials/file"),
        pathlib.Path("~/.config/launchpad-credentials"),
    ],
)
@pytest.mark.usefixtures("fs")  # Fake filesystem
def test_login_with_cache_and_credentials(mocker, cache_path, root, credentials_file):
    # Workaround for Python 3.10's interaction with pyfakefs.
    cache_path = pathlib.Path(cache_path.as_posix())

    assert not cache_path.exists()
    assert not credentials_file.exists()
    mock_login = mocker.patch.object(launchpadlib.launchpad.Launchpad, "login_with")
    launchpad.Launchpad.login(
        "craft-application-tests",
        cache_dir=cache_path,
        credentials_file=credentials_file,
        root=root,
    )

    assert cache_path.is_dir()
    assert credentials_file.parent.is_dir()
    mock_login.assert_called_once_with(
        application_name="craft-application-tests",
        service_root=root,
        launchpadlib_dir=cache_path,
        credentials_file=credentials_file,
        version="devel",
    )


@pytest.mark.usefixtures("fs")
def test_anonymous_login_no_cache_or_credentials(mocker):
    mock_login = mocker.patch.object(launchpadlib.launchpad.Launchpad, "login_with")

    launchpad.Launchpad.login(
        "craft-application-tests", cache_dir=None, credentials_file=None
    )

    mock_login.assert_called_once_with(
        application_name="craft-application-tests",
        service_root=launchpadlib.uris.LPNET_SERVICE_ROOT,
        launchpadlib_dir=None,
        credentials_file=None,
        version="devel",
    )


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


@pytest.mark.parametrize(
    ("name", "owner", "project", "path"),
    [
        ("name", "owner", "project", "~owner/project/+git/name"),
        ("name", "owner", None, "~owner/+git/name"),
    ],
)
def test_render_repository_path(
    monkeypatch, fake_launchpad, name, owner, project, path
):
    mock_get = mock.Mock()
    monkeypatch.setattr(models.GitRepository, "get", mock_get)

    fake_launchpad.get_repository(name=name, owner=owner, project=project)

    mock_get.assert_called_once_with(fake_launchpad, path=path)
