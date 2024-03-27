#  This file is part of craft-application.
#
#  Copyright 2024 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for the remote build service."""

import pytest

from craft_application import errors, launchpad


@pytest.fixture(scope="module", params=["charmcraft", "coreutils", "dpkg", "sudo"])
def public_project_name(request):
    return request.param


def test_use_public_project(anonymous_remote_build_service, public_project_name):
    """Test that we can get a real (public) project using an anonymous client."""
    anonymous_remote_build_service.set_project_name(public_project_name)
    project: launchpad.models.Project = anonymous_remote_build_service._ensure_project()

    assert project.name == public_project_name


def test_error_with_nonexistent_project(anonymous_remote_build_service):
    """Test failing gracefully with a nonexistent project."""
    name = "this launchpad project does not exist!"

    anonymous_remote_build_service.set_project_name(name)
    with pytest.raises(errors.CraftError, match="Could not find project on Launchpad"):
        anonymous_remote_build_service._ensure_project()


def test_project_is_public(anonymous_remote_build_service, public_project_name):
    """Test that the given project is public."""
    assert not anonymous_remote_build_service.is_project_private(public_project_name)
