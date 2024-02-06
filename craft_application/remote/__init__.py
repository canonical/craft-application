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

"""Remote-build and related utilities."""

from .errors import (
    AcceptPublicUploadError,
    GitError,
    RemoteBuildError,
    RemoteBuildFailedError,
    RemoteBuildInvalidGitRepoError,
    RemoteBuildTimeoutError,
    UnsupportedArchitectureError,
)
from .git import (
    GitRepo,
    GitType,
    check_git_repo_for_remote_build,
    get_git_repo_type,
    is_repo,
)
from .utils import get_build_id, humanize_list, rmtree, validate_architectures
from .worktree import WorkTree

__all__ = [
    "check_git_repo_for_remote_build",
    "get_build_id",
    "get_git_repo_type",
    "humanize_list",
    "is_repo",
    "rmtree",
    "validate_architectures",
    "AcceptPublicUploadError",
    "GitError",
    "GitRepo",
    "GitType",
    "RemoteBuildError",
    "RemoteBuildFailedError",
    "RemoteBuildInvalidGitRepoError",
    "RemoteBuildTimeoutError",
    "UnsupportedArchitectureError",
    "WorkTree",
]
