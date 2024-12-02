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

import pytest
from craft_application.git import NO_PUSH_URL, Commit, GitError, GitRepo


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
    last_commit_on_fetched_ref = git_repo.last_commit_on_branch_or_tag(
        remote=test_remote, branch_or_tag=f"{test_remote}/{ref}"
    )
    assert isinstance(
        last_commit_on_fetched_ref, Commit
    ), "There should be a commit after fetching"


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


@pytest.mark.parametrize("by_name", [True, False], ids=["by_name", "by_url"])
def test_show_remote_hello(
    empty_repository: pathlib.Path, hello_repository_lp_url: str, *, by_name: bool
) -> None:
    """Check if it is possible to fetch existing remote."""
    git_repo = GitRepo(empty_repository)
    test_remote = "test-remote"
    if by_name:
        git_repo.add_remote(test_remote, hello_repository_lp_url)
        show_remote_output = git_repo.show_remote(
            remote_name_or_url=test_remote,
            do_not_query_remotes=True,
        )
    else:
        show_remote_output = git_repo.show_remote(
            remote_name_or_url=hello_repository_lp_url,
            do_not_query_remotes=True,
        )
    assert hello_repository_lp_url in show_remote_output


def test_last_commit_on_empty_repository(empty_repository: pathlib.Path) -> None:
    """Test if last_commit errors out in empty repository."""
    git_repo = GitRepo(empty_repository)
    with pytest.raises(GitError) as git_error:
        git_repo.get_last_commit()
    assert git_error.value.details == "could not retrieve last commit"


def test_show_remote_that_does_not_exist(
    empty_repository: pathlib.Path,
) -> None:
    """Check if it is possible to fetch existing remote."""
    git_repo = GitRepo(empty_repository)
    test_remote = "test-remote"
    git_repo.add_remote(test_remote, "git+ssh://non-existing-remote.localhost")
    with pytest.raises(GitError) as git_error:
        git_repo.show_remote(remote_name_or_url=test_remote)
    assert git_error.value.details == f"cannot inspect remote: {test_remote!r}"


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
