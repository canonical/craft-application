"""Tests for anonymous access."""

import pytest
from craft_application import launchpad


def test_anonymous_login(tmp_path):
    cache_dir = tmp_path / "cache"
    assert not cache_dir.exists()

    launchpad.Launchpad.anonymous(
        "craft-application-integration-tests", root="staging", cache_dir=cache_dir
    )

    assert cache_dir.is_dir()


# TODO: Re-enable this
# https://github.com/canonical/craft-application/issues/306
# def test_get_basic_items(anonymous_lp):
#     snapstore_server = anonymous_lp.get_project("snapstore-server")
#     assert snapstore_server.name == "snapstore-server"
#     assert snapstore_server.title == "Snap Store Server"
#
#     snap_recipes = list(models.SnapRecipe.find(anonymous_lp, owner="lengau"))
#     assert len(snap_recipes) > 0
#     for recipe in snap_recipes:
#         assert recipe.owner_name == "lengau"


@pytest.mark.parametrize(
    ("name", "path"),
    [
        ("python-apt", "~deity/python-apt/+git/python-apt"),
        ("charmcraft", "~charmcraft-team/charmcraft/+git/charmcraft"),
    ],
)
def test_get_real_repository_by_path(anonymous_lp, name, path):
    repo = anonymous_lp.get_repository(path=path)

    assert repo.git_https_url.endswith(name)
    assert repo.name == name


@pytest.mark.parametrize(
    ("name", "owner", "project"),
    [
        ("python-apt", "deity", "python-apt"),
        ("charmcraft", "charmcraft-team", "charmcraft"),
        ("snapcraft", "canonical-starcraft", "snapcraft"),
    ],
)
def test_get_real_repository_by_name(anonymous_lp, name, owner, project):
    repo = anonymous_lp.get_repository(name=name, owner=owner, project=project)

    assert repo.name == name
    assert repo.owner_name == owner
