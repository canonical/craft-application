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
from craft_application.git import Commit, GitError, GitRepo


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
