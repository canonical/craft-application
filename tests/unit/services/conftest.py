# This file is part of craft_application.
#
# Copyright 2024 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Configuration for craft-application unit tests."""
from __future__ import annotations

from collections.abc import Callable
from unittest import mock

import launchpadlib.launchpad
import lazr.restfulclient.resource
import pytest
from craft_application import launchpad, services


def get_mock_lazr_collection(item, **kwargs):
    """Get a mock of a lazr collection."""
    collection = mock.MagicMock(
        spec=lazr.restfulclient.resource.Collection, name="MockLazrCollection"
    )
    collection.configure_mock(**kwargs)
    collection.__getitem__.return_value = item
    return collection


def get_mock_lazr_entry(resource_type, **kwargs):
    """Get a Mock of a lazr entry."""
    entry = mock.MagicMock(
        spec=lazr.restfulclient.resource.Entry,
        name="MockLazrEntry",
        resource_type_link=f"https://api.launchpad.net/devel#{resource_type}",
    )
    entry.configure_mock(**kwargs)
    return entry


def get_mock_callable(**kwargs):
    return mock.Mock(spec_set=Callable, **kwargs)


@pytest.fixture
def mock_project_entry():
    return get_mock_lazr_entry(
        resource_type="project",
        name="craft_test_user-craft-remote-build",
    )


@pytest.fixture
def mock_git_repository():
    return get_mock_lazr_entry(
        "git_repository",
        issueAccessToken=mock.Mock(spec=Callable, return_value="super_secret_token"),
        git_https_url="https://git.launchpad.net/",
    )


@pytest.fixture
def fake_launchpad(app_metadata, mock_git_repository, mock_project_entry):
    me = mock.Mock(lazr.restfulclient.resource.Entry)
    me.name = "craft_test_user"
    lp = mock.Mock(
        spec=launchpadlib.launchpad.Launchpad,
        me=me,
        projects=get_mock_lazr_collection(
            mock_project_entry,
            new_project=get_mock_callable(return_value=mock_project_entry),
        ),
        git_repositories=get_mock_lazr_collection(
            mock_git_repository,
            new=get_mock_callable(return_value=mock_git_repository),
        ),
        snaps=get_mock_lazr_collection(
            None,
            new=get_mock_callable(
                return_value=get_mock_lazr_entry(
                    "snap",
                    requestBuilds=get_mock_callable(
                        return_value=get_mock_lazr_collection(
                            [], status="Completed", builds=[]
                        )
                    ),
                )
            ),
            getByName=get_mock_callable(
                return_value=get_mock_lazr_entry(
                    "snap",
                    requestBuilds=get_mock_callable(
                        return_value=get_mock_lazr_collection(
                            [], status="Completed", builds=[]
                        )
                    ),
                ),
            ),
        ),
    )
    return launchpad.Launchpad(app_metadata.name, lp)


@pytest.fixture
def remote_build_service(app_metadata, fake_services, fake_launchpad):
    class FakeRemoteBuildService(services.RemoteBuildService):
        RecipeClass = launchpad.models.SnapRecipe

    service = FakeRemoteBuildService(
        app_metadata,
        fake_services,
    )
    service.lp = fake_launchpad
    return service
