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

from craft_application.remote import errors


def test_git_error():
    """Test RemoteBuildGitError."""
    error = errors.RemoteBuildGitError(message="failed to push some refs to 'unknown'")

    assert (
        str(error) == "Git operation failed with: failed to push some refs to 'unknown'"
    )


def test_unsupported_architecture_error():
    """Test UnsupportedArchitectureError."""
    error = errors.UnsupportedArchitectureError(architectures=["amd64", "arm64"])

    assert str(error) == (
        "The following architectures are not supported by the remote builder: "
        "'amd64' and 'arm64'."
    )
    assert error.resolution == "Remove them from the architecture list and try again."
