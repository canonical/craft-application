# Copyright 2023-2024 Canonical Ltd.
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

"""Git repository class and helper utilities."""

from pathlib import Path

from craft_application.git import GitType, get_git_repo_type

from .errors import RemoteBuildInvalidGitRepoError


def check_git_repo_for_remote_build(path: Path) -> None:
    """Check if a directory meets the requirements of doing remote builds.

    :param path: filepath to check

    :raises RemoteBuildInvalidGitRepoError: if incompatible git repo is found
    """
    git_type = get_git_repo_type(path.absolute())

    if git_type == GitType.INVALID:
        raise RemoteBuildInvalidGitRepoError(
            message=f"Could not find a git repository in {str(path)!r}",
            resolution="Initialize a git repository in the project directory",
        )

    if git_type == GitType.SHALLOW:
        raise RemoteBuildInvalidGitRepoError(
            message="Remote builds for shallow cloned git repos are not supported",
            resolution="Make a non-shallow clone of the repository",
        )
