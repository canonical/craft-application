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

"""Git repository utilities."""

from ._consts import (
    NO_PUSH_URL,
    COMMIT_SHA_LEN,
    COMMIT_SHORT_SHA_LEN,
    CRAFTGIT_BINARY_NAME,
    GIT_FALLBACK_BINARY_NAME,
)
from ._errors import GitError
from ._models import GitType, Commit, short_commit_sha

from ._git_repo import (
    GitRepo,
    get_git_repo_type,
    is_repo,
    is_commit,
    is_short_commit,
    parse_describe,
)

__all__ = [
    "GitError",
    "GitRepo",
    "GitType",
    "Commit",
    "get_git_repo_type",
    "is_repo",
    "parse_describe",
    "is_commit",
    "is_short_commit",
    "short_commit_sha",
    "NO_PUSH_URL",
    "COMMIT_SHA_LEN",
    "COMMIT_SHORT_SHA_LEN",
    "CRAFTGIT_BINARY_NAME",
    "GIT_FALLBACK_BINARY_NAME",
]
