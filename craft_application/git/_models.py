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

"""Git repository models."""

from dataclasses import dataclass
from enum import Enum

from ._consts import COMMIT_SHORT_SHA_LEN


def short_commit_sha(commit_sha: str) -> str:
    """Return shortened version of the commit."""
    return commit_sha[:COMMIT_SHORT_SHA_LEN]


class GitType(Enum):
    """Type of git repository."""

    INVALID = 0
    NORMAL = 1
    SHALLOW = 2


@dataclass
class Commit:
    """Model representing a commit."""

    sha: str
    message: str

    @property
    def short_sha(self) -> str:
        """Get short commit sha."""
        return short_commit_sha(self.sha)
