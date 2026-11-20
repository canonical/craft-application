#  This file is part of craft-application.
#
#  Copyright 2026 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Unit tests for the clone method of SourceStoreService."""

import pathlib
import typing
from unittest.mock import MagicMock, call
from urllib.parse import urlparse

import pytest
import pytest_mock
from craft_application import errors, models
from craft_application.git import GitRepo
from craft_application.services.sourcestore import SourceStoreService
from craft_application.services.sourcestore.source_store_service import _parse_channel
from craft_cli.pytest_plugin import RecordingEmitter
from craft_store import creds
from craft_store.models import Plane
from craft_store.publisher import (
    ORIGIN_REMOTE_NAME,
    STORE_REMOTE_NAME,
    UPSTREAM_REMOTE_NAME,
    Remote,
)


@pytest.fixture
def git_repo(mocker: pytest_mock.MockerFixture) -> MagicMock:
    return mocker.patch(
        "craft_application.services.sourcestore.source_store_service.GitRepo",
        spec=GitRepo,
    )


def _get_emitter_interactions(
    *,
    branch: str,
    plane: Plane | None,
    fake_origin: Remote | None = None,
    fake_upstream: Remote | None = None,
) -> list[typing.Any]:
    interactions = [
        call(
            "progress",
            f"Cloning sources from Source Store (branch: {branch!r})",
        ),
        call("trace", "Updating remote URL to remove credentials"),
    ]
    if plane is not None:
        interactions.append(
            call("debug", f"Setting plane in repository to {plane.name!r}")
        )

    if fake_origin is not None:
        interactions.append(
            call("progress", f"Setting {ORIGIN_REMOTE_NAME!r} to {fake_origin.url!r}")
        )
    else:
        interactions.append(call("debug", "Origin not available, skipping..."))

    if fake_upstream is not None:
        interactions.append(
            call(
                "progress", f"Setting {UPSTREAM_REMOTE_NAME!r} to {fake_upstream.url!r}"
            )
        )
    return interactions


def test_clone(
    source_store: SourceStoreService,
    fake_project: models.Project,
    craft_publisher_gw_client_mock: MagicMock,
    empty_project_dir: pathlib.Path,
    emitter: RecordingEmitter,
    git_repo: MagicMock,
    default_plane: Plane | None,
    fake_dev_token: creds.DeveloperToken,
    fake_store: Remote,
    fake_origin: Remote,
    fake_upstream: Remote,
) -> None:
    project_name = fake_project.name
    parsed_url = urlparse(fake_store.url)

    channel = "test/edge"
    repository_branch = _parse_channel(channel)
    craft_publisher_gw_client_mock.get_remotes.return_value = [
        fake_store,
        fake_origin,
        fake_upstream,
    ]
    source_store.clone(
        name=project_name,
        plane=default_plane,
        channel=channel,
        cloning_path=empty_project_dir,
    )
    craft_publisher_gw_client_mock.get_remotes.assert_called_with(
        channel=channel,
        package_name=project_name,
        plane=default_plane,
    )
    git_repo.clone_repository.assert_called_with(
        checkout_branch=repository_branch,
        path=empty_project_dir,
        url=f"https://{source_store.clone_user}:{fake_dev_token.macaroon}@{parsed_url.netloc}",
    )
    git_repo_obj = git_repo.clone_repository.return_value
    git_repo_obj.set_remote_url.assert_called_with(
        ORIGIN_REMOTE_NAME,
        fake_store.url,
    )
    git_repo_obj.rename_remote.assert_called_with(ORIGIN_REMOTE_NAME, STORE_REMOTE_NAME)
    assert git_repo_obj.set_no_push.mock_calls == [
        call(STORE_REMOTE_NAME),
        call(UPSTREAM_REMOTE_NAME),
    ]
    assert git_repo_obj.add_remote.mock_calls == [
        call(ORIGIN_REMOTE_NAME, fake_origin.url),
        call(UPSTREAM_REMOTE_NAME, fake_upstream.url),
    ]

    emitter.assert_interactions(
        _get_emitter_interactions(
            branch=repository_branch,
            plane=default_plane,
            fake_origin=fake_origin,
            fake_upstream=fake_upstream,
        )
    )


def test_clone_no_store(
    source_store: SourceStoreService,
    fake_project: models.Project,
    craft_publisher_gw_client_mock: MagicMock,
    empty_project_dir: pathlib.Path,
    default_plane: Plane | None,
) -> None:
    project_name = fake_project.name

    channel = "test/edge"
    craft_publisher_gw_client_mock.get_remotes.return_value = []
    with pytest.raises(
        errors.StoreRemoteUnvailableError,
        match=f"Package {project_name!r} does not have store remote.",
    ):
        source_store.clone(
            name=project_name,
            plane=default_plane,
            channel=channel,
            cloning_path=empty_project_dir,
        )


def test_clone_no_origin(
    source_store: SourceStoreService,
    fake_project: models.Project,
    craft_publisher_gw_client_mock: MagicMock,
    empty_project_dir: pathlib.Path,
    emitter: RecordingEmitter,
    git_repo: MagicMock,
    default_plane: Plane | None,
    fake_dev_token: creds.DeveloperToken,
    fake_store: Remote,
    fake_upstream: Remote,
) -> None:
    project_name = fake_project.name
    parsed_url = urlparse(fake_store.url)

    channel = "test/edge"
    repository_branch = _parse_channel(channel)
    craft_publisher_gw_client_mock.get_remotes.return_value = [
        fake_store,
        fake_upstream,
    ]
    source_store.clone(
        name=project_name,
        plane=default_plane,
        channel=channel,
        cloning_path=empty_project_dir,
    )
    craft_publisher_gw_client_mock.get_remotes.assert_called_with(
        channel=channel,
        package_name=project_name,
        plane=default_plane,
    )
    git_repo.clone_repository.assert_called_with(
        checkout_branch=repository_branch,
        path=empty_project_dir,
        url=f"https://{source_store.clone_user}:{fake_dev_token.macaroon}@{parsed_url.netloc}",
    )
    git_repo_obj = git_repo.clone_repository.return_value
    git_repo_obj.set_remote_url.assert_called_with(
        ORIGIN_REMOTE_NAME,
        fake_store.url,
    )
    git_repo_obj.rename_remote.assert_called_with(ORIGIN_REMOTE_NAME, STORE_REMOTE_NAME)
    assert git_repo_obj.set_no_push.mock_calls == [
        call(STORE_REMOTE_NAME),
        call(UPSTREAM_REMOTE_NAME),
    ]
    assert git_repo_obj.add_remote.mock_calls == [
        call(UPSTREAM_REMOTE_NAME, fake_upstream.url),
    ]

    emitter.assert_interactions(
        _get_emitter_interactions(
            branch=repository_branch, plane=default_plane, fake_upstream=fake_upstream
        )
    )


def test_clone_no_upstream_and_origin(
    source_store: SourceStoreService,
    fake_project: models.Project,
    craft_publisher_gw_client_mock: MagicMock,
    empty_project_dir: pathlib.Path,
    emitter: RecordingEmitter,
    git_repo: MagicMock,
    default_plane: Plane | None,
    fake_dev_token: creds.DeveloperToken,
    fake_store: Remote,
) -> None:
    project_name = fake_project.name
    parsed_url = urlparse(fake_store.url)

    channel = "test/edge"
    repository_branch = _parse_channel(channel)
    craft_publisher_gw_client_mock.get_remotes.return_value = [fake_store]
    source_store.clone(
        name=project_name,
        plane=default_plane,
        channel=channel,
        cloning_path=empty_project_dir,
    )
    craft_publisher_gw_client_mock.get_remotes.assert_called_with(
        channel=channel,
        package_name=project_name,
        plane=default_plane,
    )
    git_repo.clone_repository.assert_called_with(
        checkout_branch=repository_branch,
        path=empty_project_dir,
        url=f"https://{source_store.clone_user}:{fake_dev_token.macaroon}@{parsed_url.netloc}",
    )
    git_repo_obj = git_repo.clone_repository.return_value
    git_repo_obj.set_remote_url.assert_called_with(
        ORIGIN_REMOTE_NAME,
        fake_store.url,
    )
    git_repo_obj.rename_remote.assert_called_with(ORIGIN_REMOTE_NAME, STORE_REMOTE_NAME)
    assert git_repo_obj.set_no_push.mock_calls == [
        call(STORE_REMOTE_NAME),
    ]
    assert git_repo_obj.add_remote.mock_calls == []

    emitter.assert_interactions(
        _get_emitter_interactions(branch=repository_branch, plane=default_plane)
    )
