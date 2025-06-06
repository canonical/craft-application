# This file is part of starcraft.
#
# Copyright 2024 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Git module integration tests."""

import pathlib
import re

import pytest
from craft_application.git import NO_PUSH_URL, Commit, GitError, GitRepo


@pytest.fixture
def git_repo(empty_repository: pathlib.Path) -> GitRepo:
    return GitRepo(empty_repository)


@pytest.mark.slow
def test_fetching_hello_repository(
    empty_repository: pathlib.Path,
    hello_repository_lp_url: str,
) -> None:
    """Check if it is possible to fetch existing remote."""
    git_repo = GitRepo(empty_repository)
    test_remote = "test-remote"
    ref = "ubuntu/noble"
    git_repo.add_remote(test_remote, hello_repository_lp_url)
    git_repo.fetch(remote=test_remote, ref=ref, depth=1)
    last_commit_on_fetched_ref = git_repo.get_last_commit_on_branch_or_tag(
        remote=test_remote, branch_or_tag=f"{test_remote}/{ref}"
    )
    assert isinstance(last_commit_on_fetched_ref, Commit), (
        "There should be a commit after fetching"
    )


def test_fetching_remote_that_does_not_exist(
    empty_repository: pathlib.Path,
) -> None:
    """Check if it is possible to fetch existing remote."""
    git_repo = GitRepo(empty_repository)
    test_remote = "test-remote"
    ref = "ubuntu/noble"
    git_repo.add_remote(test_remote, "git+ssh://non-existing-remote.localhost")
    with pytest.raises(GitError) as git_error:
        git_repo.fetch(remote=test_remote, ref=ref, depth=1)
    assert git_error.value.details == f"cannot fetch remote: {test_remote!r}"


def test_set_url(empty_repository: pathlib.Path, hello_repository_lp_url: str) -> None:
    """Check if remote URL can be set using API."""
    new_remote_url = "https://non-existing-remote-url.localhost"
    git_repo = GitRepo(empty_repository)
    test_remote = "test-remote"
    git_repo.add_remote(test_remote, hello_repository_lp_url)
    assert git_repo.get_remote_url(remote_name=test_remote) == hello_repository_lp_url
    assert git_repo.get_remote_push_url(remote_name=test_remote) is None

    git_repo.set_remote_url(test_remote, new_remote_url)
    assert git_repo.get_remote_url(remote_name=test_remote) == new_remote_url
    assert git_repo.get_remote_push_url(remote_name=test_remote) is None


def test_set_push_url(
    empty_repository: pathlib.Path, hello_repository_lp_url: str
) -> None:
    """Check if remote push URL can be set using API."""
    new_remote_push_url = "https://non-existing-remote-push-url.localhost"
    git_repo = GitRepo(empty_repository)
    test_remote = "test-remote"
    git_repo.add_remote(test_remote, hello_repository_lp_url)
    assert git_repo.get_remote_url(remote_name=test_remote) == hello_repository_lp_url
    assert git_repo.get_remote_push_url(remote_name=test_remote) is None

    git_repo.set_remote_push_url(test_remote, new_remote_push_url)
    assert git_repo.get_remote_url(remote_name=test_remote) == hello_repository_lp_url
    assert git_repo.get_remote_push_url(remote_name=test_remote) == new_remote_push_url


def test_set_no_push(
    empty_repository: pathlib.Path, hello_repository_lp_url: str
) -> None:
    """Check if remote push URL can be set using API."""
    git_repo = GitRepo(empty_repository)
    test_remote = "test-remote"
    git_repo.add_remote(test_remote, hello_repository_lp_url)
    assert git_repo.get_remote_url(remote_name=test_remote) == hello_repository_lp_url
    assert git_repo.get_remote_push_url(remote_name=test_remote) is None

    git_repo.set_no_push(test_remote)
    assert git_repo.get_remote_url(remote_name=test_remote) == hello_repository_lp_url
    assert git_repo.get_remote_push_url(remote_name=test_remote) == NO_PUSH_URL


@pytest.mark.parametrize(
    ("config_key", "expected_value"),
    [("core.bare", "false"), ("non_existent.key", None)],
)
def test_get_repo_configuration(
    git_repo: GitRepo, config_key: str, expected_value: str | None
) -> None:
    assert git_repo.get_config_value(config_key) == expected_value


def test_set_repo_configuration(git_repo: GitRepo) -> None:
    new_key = "test.craft"
    new_value = "just-testing"
    assert git_repo.get_config_value(new_key) is None
    git_repo.set_config_value(new_key, new_value)
    assert git_repo.get_config_value(new_key) == new_value


def test_update_repo_configuration(git_repo: GitRepo) -> None:
    key = "test.craft"
    old_value = "just-old"
    new_value = "just-new"
    git_repo.set_config_value(key, old_value)
    assert git_repo.get_config_value(key) == old_value
    git_repo.set_config_value(key, new_value)
    assert git_repo.get_config_value(key) == new_value


def test_update_boolean_with_string_value(git_repo: GitRepo) -> None:
    key = "core.bare"
    new_value = "incorrect-boolean"
    # this makes repository inaccessible via git CLI client
    # fatal: bad boolean config value 'incorrect-boolean' for 'core.bare'
    git_repo.set_config_value(key, new_value)
    assert git_repo.get_config_value(key) == new_value


def test_incorrect_config_key(git_repo: GitRepo) -> None:
    key = "craft.incorrect&test*key"
    new_value = "not-important"
    with pytest.raises(
        ValueError, match=re.escape(f"invalid config item name {key!r}")
    ):
        git_repo.set_config_value(key, new_value)
