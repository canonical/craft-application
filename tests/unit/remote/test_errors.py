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
    """Test GitError."""
    error = errors.GitError("Error details.")

    assert str(error) == "Git operation failed.\nError details."
    assert (
        repr(error)
        == "GitError(brief='Git operation failed.', details='Error details.')"
    )
    assert error.brief == "Git operation failed."
    assert error.details == "Error details."


def test_unsupported_architecture_error():
    """Test UnsupportedArchitectureError."""
    error = errors.UnsupportedArchitectureError(architectures=["amd64", "arm64"])

    assert str(error) == (
        "Architecture not supported by the remote builder.\nThe following "
        "architectures are not supported by the remote builder: ['amd64', 'arm64'].\n"
        "Please remove them from the architecture list and try again."
    )
    assert repr(error) == (
        "UnsupportedArchitectureError(brief='Architecture not supported by the remote "
        "builder.', details=\"The following architectures are not supported by the "
        "remote builder: ['amd64', 'arm64'].\\nPlease remove them from the "
        'architecture list and try again.")'
    )

    assert error.brief == "Architecture not supported by the remote builder."
    assert error.details == (
        "The following architectures are not supported by the remote builder: "
        "['amd64', 'arm64'].\nPlease remove them from the architecture list and "
        "try again."
    )
