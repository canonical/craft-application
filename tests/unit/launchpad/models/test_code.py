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
"""Unit tests for source repositories."""

import pytest
from craft_application.launchpad.models import InformationType, code


@pytest.mark.parametrize("name", ["repo_name", "my_repo"])
@pytest.mark.parametrize(
    ("owner", "owner_path"),
    [
        ("owner", "/~owner"),
        (None, "/~test_user"),
    ],
)
@pytest.mark.parametrize(
    ("target", "target_path"),
    [("project", "/project")],
)
@pytest.mark.parametrize("information_type", InformationType)
def test_new_repository_with_target(
    fake_launchpad,
    mock_lplib_entry,
    name,
    owner,
    owner_path,
    target,
    target_path,
    information_type,
):
    mock_lplib_entry.resource_type_link = "http://localhost#git_repository"
    fake_launchpad.lp.git_repositories.new.return_value = mock_lplib_entry

    code.GitRepository.new(fake_launchpad, name, owner, target, information_type)

    fake_launchpad.lp.git_repositories.new.assert_called_once_with(
        name=name,
        owner=owner_path,
        target=target_path,
        information_type=information_type.value,
    )


@pytest.mark.parametrize("name", ["repo_name", "my_repo"])
@pytest.mark.parametrize(
    ("owner", "owner_path"),
    [
        ("owner", "/~owner"),
        (None, "/~test_user"),
    ],
)
@pytest.mark.parametrize("information_type", InformationType)
def test_new_repository_without_target(
    fake_launchpad, mock_lplib_entry, name, owner, owner_path, information_type
):
    mock_lplib_entry.resource_type_link = "http://localhost#git_repository"
    fake_launchpad.lp.git_repositories.new.return_value = mock_lplib_entry

    code.GitRepository.new(
        fake_launchpad, name, owner, information_type=information_type
    )

    fake_launchpad.lp.git_repositories.new.assert_called_once_with(
        name=name, owner=owner_path, information_type=information_type.value
    )
