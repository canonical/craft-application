# Copyright 2024 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Remote-build git tests."""

import pytest
from craft_application.git import GitType
from craft_application.remote import errors, git


@pytest.fixture
def mock_get_git_repo_type(mocker):
    return mocker.patch("craft_application.remote.git.get_git_repo_type")


def test_git_normal(tmp_path, mock_get_git_repo_type):
    """No-op for a normal git repo."""
    mock_get_git_repo_type.return_value = GitType.NORMAL

    assert git.check_git_repo_for_remote_build(tmp_path) is None


def test_git_invalid_error(tmp_path, mock_get_git_repo_type):
    """Raise an error for invalid git repos."""
    mock_get_git_repo_type.return_value = GitType.INVALID

    with pytest.raises(errors.RemoteBuildInvalidGitRepoError) as err:
        git.check_git_repo_for_remote_build(tmp_path)

    assert str(err.value) == f"Could not find a git repository in {str(tmp_path)!r}"
    assert (
        err.value.resolution == "Initialize a git repository in the project directory"
    )


def test_git_shallow_clone_error(tmp_path, mock_get_git_repo_type):
    """Raise an error for shallowly cloned repos."""
    mock_get_git_repo_type.return_value = GitType.SHALLOW

    with pytest.raises(errors.RemoteBuildInvalidGitRepoError) as err:
        git.check_git_repo_for_remote_build(tmp_path)

    assert (
        str(err.value) == "Remote builds for shallow cloned git repos are not supported"
    )
    assert err.value.resolution == "Make a non-shallow clone of the repository"
