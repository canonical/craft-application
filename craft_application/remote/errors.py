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

import craft_cli.errors

from craft_application.util import humanize_list


class RemoteBuildError(craft_cli.errors.CraftError):
    """Error for remote builds."""


class RemoteBuildGitError(RemoteBuildError):
    """Git repository cannot be prepared correctly.

    :param message: Git error message.
    """

    def __init__(self, message: str) -> None:
        message = f"Git operation failed with: {message}"
        super().__init__(message=message)


class UnsupportedArchitectureError(RemoteBuildError):
    """Unsupported architecture error.

    :param architectures: List of unsupported architectures.
    """

    def __init__(self, architectures: list[str]) -> None:
        message = (
            "The following architectures are not supported by the remote builder: "
            f"{humanize_list(architectures, 'and')}."
        )
        resolution = "Remove them from the architecture list and try again."

        super().__init__(message=message, resolution=resolution)


class RemoteBuildInvalidGitRepoError(RemoteBuildError):
    """The Git repository is invalid for remote build."""
