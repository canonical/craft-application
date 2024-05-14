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

"""Remote build errors."""

from dataclasses import dataclass


@dataclass(repr=True)
class RemoteBuildError(Exception):
    """Unexpected remote build error.

    :param brief: Brief description of error.
    :param details: Detailed information.
    """

    brief: str
    details: str | None = None

    def __str__(self) -> str:
        """Return the string representation of the error."""
        components = [self.brief]

        if self.details:
            components.append(self.details)

        return "\n".join(components)


class GitError(RemoteBuildError):
    """Git is not working as expected."""

    def __init__(self, message: str) -> None:
        self.message = message
        brief = "Git operation failed."
        details = message

        super().__init__(brief=brief, details=details)


class UnsupportedArchitectureError(RemoteBuildError):
    """Unsupported architecture error."""

    def __init__(self, architectures: list[str]) -> None:
        brief = "Architecture not supported by the remote builder."
        details = (
            "The following architectures are not supported by the remote builder: "
            f"{architectures}.\nPlease remove them from the "
            "architecture list and try again."
        )

        super().__init__(brief=brief, details=details)


class RemoteBuildInvalidGitRepoError(RemoteBuildError):
    """The Git repository is invalid for remote build.

    :param brief: Brief description of error.
    :param details: Detailed information.
    """

    def __init__(self, details: str) -> None:
        brief = "The Git repository is invalid for remote build."

        super().__init__(brief=brief, details=details)
