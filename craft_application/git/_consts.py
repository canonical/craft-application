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

"""Git repository consts."""

from typing import Final

NO_PUSH_URL: Final[str] = "no_push"

COMMIT_SHA_LEN: Final[int] = 40

COMMIT_SHORT_SHA_LEN: Final[int] = 7

CRAFTGIT_BINARY_NAME: Final[str] = "craft.git"

GIT_FALLBACK_BINARY_NAME: Final[str] = "git"
