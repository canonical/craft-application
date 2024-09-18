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
import datetime
import pathlib
from unittest import mock

import launchpadlib.errors
import lazr.restfulclient.errors
import lazr.restfulclient.resource
import platformdirs
import pytest
from craft_application import errors, git, launchpad, services
from craft_application.remote.errors import (
    RemoteBuildGitError,
    RemoteBuildInvalidGitRepoError,
)

from tests.unit.services.conftest import (
    get_mock_callable,
)


@pytest.fixture
def mock_push_url(monkeypatch):
    push_url = get_mock_callable(return_value=None)
    monkeypatch.setattr(git.GitRepo, "push_url", push_url)
    return push_url


@pytest.fixture
def mock_push_url_raises_git_error(monkeypatch):
    push_url = get_mock_callable(
        side_effect=git.GitError("Fake push_url error during tests")
    )
    monkeypatch.setattr(git.GitRepo, "push_url", push_url)
    return push_url


@pytest.fixture
def mock_init_raises_git_error(monkeypatch):
    git_repo_init = get_mock_callable(
        side_effect=git.GitError("Fake _init_repo error during tests")
    )
    monkeypatch.setattr(git.GitRepo, "_init_repo", git_repo_init)
    return git_repo_init


@pytest.fixture
def mock_lp_project(fake_launchpad, mock_project_entry):
    return launchpad.models.Project(fake_launchpad, mock_project_entry)


@pytest.mark.parametrize("name", ["some-project", "another-project"])
def test_set_project_success(remote_build_service, mock_project_entry, name):
    mock_project_entry.name = name
    remote_build_service.lp.lp.projects = {name: mock_project_entry}

    remote_build_service.set_project(name)
    project = remote_build_service._ensure_project()

    assert project.name == name


@pytest.mark.parametrize("name", ["some-project", "another-project"])
def test_set_project_name_error(remote_build_service, mock_project_entry, name, mocker):
    mocker.patch("time.sleep")
    mock_project_entry.name = name
    response = mocker.Mock(
        status=400, reason="Bad Request", items=mocker.Mock(return_value=[])
    )
    remote_build_service.lp.lp.projects.__getitem__.side_effect = (
        lazr.restfulclient.errors.NotFound(response, "dawg")
    )

    with pytest.raises(
        errors.CraftError, match=f"Could not find project on Launchpad: {name}"
    ) as exc_info:
        remote_build_service.set_project(name)

    assert (
        exc_info.value.resolution
        == "Ensure the project exists and that you have access to it."
    )


def test_ensure_project_existing(remote_build_service, mock_project_entry):
    remote_build_service.lp.lp.projects = {
        "craft_test_user-craft-remote-build": mock_project_entry
    }

    remote_build_service._ensure_project()


def test_ensure_project_new(remote_build_service, mocker):
    mocker.patch("time.sleep")
    response = mocker.Mock(
        status=400, reason="Bad Request", items=mocker.Mock(return_value=[])
    )
    remote_build_service.lp.lp.projects.__getitem__.side_effect = (
        lazr.restfulclient.errors.NotFound(response, "dawg")
    )

    remote_build_service._ensure_project()


@pytest.mark.parametrize(
    ("information_type", "expected"),
    [
        (launchpad.models.InformationType.PUBLIC, False),
        (launchpad.models.InformationType.PUBLIC_SECURITY, False),
        (launchpad.models.InformationType.PRIVATE, True),
        (launchpad.models.InformationType.PRIVATE_SECURITY, True),
        (launchpad.models.InformationType.PROPRIETARY, True),
        (launchpad.models.InformationType.EMBARGOED, True),
    ],
)
def test_is_project_private(
    remote_build_service, mock_project_entry, information_type, expected
):
    mock_project_entry.information_type = str(information_type.value)
    remote_build_service.lp.lp.projects = {"test-project": mock_project_entry}

    remote_build_service.set_project("test-project")
    assert remote_build_service.is_project_private() == expected


def test_is_project_private_error(remote_build_service):
    with pytest.raises(
        RuntimeError,
        match="Cannot check if the project is private before setting its name.",
    ):
        remote_build_service.is_project_private()


def test_ensure_repository_creation(
    monkeypatch, tmp_path, remote_build_service, mock_lp_project, mock_push_url
):
    wrapped_repository = mock.Mock(
        spec=launchpad.models.GitRepository,
        git_https_url="https://git.launchpad.net/~user/+git/my_repo",
        **{"get_access_token.return_value": "super_secret_token"},
    )
    repository_new = mock.Mock(return_value=wrapped_repository)
    monkeypatch.setattr(launchpad.models.GitRepository, "new", repository_new)
    sentinel = tmp_path / "sentinel_file"
    sentinel.write_text("I am a sentinel file.")
    remote_build_service._lp_project = mock_lp_project

    work_tree, lp_repository = remote_build_service._ensure_repository(tmp_path)

    assert (work_tree.repo_dir / "sentinel_file").read_text() == sentinel.read_text()
    mock_push_url.assert_called_once_with(
        "https://craft_test_user:super_secret_token@git.launchpad.net/~user/+git/my_repo",
        "main",
        push_tags=True,
    )
    expiry = wrapped_repository.get_access_token.call_args.kwargs["expiry"]

    # Ensure that we're getting a timezone-aware object in the method.
    # This is here as a regression test because if you're in a timezone behind UTC
    # the expiry time sent to Launchpad will have already expired and Launchpad
    # does not catch that. So instead we make sure thot even when using the easternmost
    # time zone the expiry time is still in the future.
    tz = datetime.timezone(datetime.timedelta(hours=14))
    assert expiry > datetime.datetime.now(tz=tz)


@pytest.mark.usefixtures("mock_push_url_raises_git_error")
def test_ensure_repository_wraps_git_error_on_pushing(
    monkeypatch,
    tmp_path,
    remote_build_service,
    mock_lp_project,
):
    wrapped_repository = mock.Mock(
        spec=launchpad.models.GitRepository,
        git_https_url="https://git.launchpad.net/~user/+git/my_repo",
        **{"get_access_token.return_value": "super_secret_token"},
    )
    repository_new = mock.Mock(return_value=wrapped_repository)

    monkeypatch.setattr(launchpad.models.GitRepository, "new", repository_new)
    sentinel = tmp_path / "sentinel_file"
    sentinel.write_text("I am a sentinel file.")
    remote_build_service._lp_project = mock_lp_project

    with pytest.raises(RemoteBuildGitError, match="Fake push_url error during tests"):
        remote_build_service._ensure_repository(tmp_path)


@pytest.mark.usefixtures("mock_init_raises_git_error")
def test_ensure_repository_wraps_git_error_during_init(
    tmp_path,
    remote_build_service,
):
    with pytest.raises(RemoteBuildGitError, match="Fake _init_repo error during tests"):
        remote_build_service._ensure_repository(tmp_path)


def test_ensure_repository_already_exists(
    monkeypatch, tmp_path, remote_build_service, mock_lp_project, mock_push_url
):
    monkeypatch.setattr(
        launchpad.models.GitRepository,
        "new",
        mock.Mock(side_effect=launchpadlib.errors.Conflict("nope", "broken")),
    )
    wrapped_repository = mock.Mock(
        spec=launchpad.models.GitRepository,
        git_https_url="https://git.launchpad.net/~user/+git/my_repo",
        **{"get_access_token.return_value": "super_secret_token"},
    )
    repository_get = mock.Mock(return_value=wrapped_repository)
    monkeypatch.setattr(launchpad.models.GitRepository, "get", repository_get)
    sentinel = tmp_path / "sentinel_file"
    sentinel.write_text("I am a sentinel file.")
    remote_build_service._lp_project = mock_lp_project
    remote_build_service._name = "some-repo-name"

    work_tree, lp_repository = remote_build_service._ensure_repository(tmp_path)

    assert (work_tree.repo_dir / "sentinel_file").read_text() == sentinel.read_text()
    mock_push_url.assert_called_once_with(
        "https://craft_test_user:super_secret_token@git.launchpad.net/~user/+git/my_repo",
        "main",
        push_tags=True,
    )
    expiry = wrapped_repository.get_access_token.call_args.kwargs["expiry"]

    # Ensure that we're getting a timezone-aware object in the method.
    # This is here as a regression test because if you're in a timezone behind UTC
    # the expiry time sent to Launchpad will have already expired and Launchpad
    # does not catch that. So instead we make sure thot even when using the easternmost
    # time zone the expiry time is still in the future.
    tz = datetime.timezone(datetime.timedelta(hours=14))
    assert expiry > datetime.datetime.now(tz=tz)


def test_create_new_recipe(remote_build_service, mock_lp_project):
    """Test that _new_recipe works correctly."""
    remote_build_service._lp_project = mock_lp_project
    remote_build_service.RecipeClass = mock.Mock()
    repo = mock.Mock(git_https_url="https://localhost/~me/some-project/+git/my-repo")

    remote_build_service._new_recipe("test-recipe", repo)

    remote_build_service.RecipeClass.new.assert_called_once_with(
        remote_build_service.lp,
        "test-recipe",
        "craft_test_user",
        git_ref="/~me/some-project/+git/my-repo/+ref/main",
        project="craft_test_user-craft-remote-build",
    )


@pytest.mark.parametrize(
    ("archs", "expected_archs"),
    [
        (None, None),
        ([], []),
        (["amd64"], ["amd64"]),
        (["amd64", "amd64"], ["amd64", "amd64"]),
        pytest.param(["all"], ["amd64"], id="all-to-amd64"),
        # craft-application's Project model does not allow 'all' with other archs but
        # RemoteBuild service should still handle this scenario
        pytest.param(
            ["amd64", "s390x", "all"], ["amd64", "s390x", "amd64"], id="all-with-others"
        ),
    ],
)
def test_create_new_recipe_archs(
    archs, expected_archs, remote_build_service, mock_lp_project
):
    """Test that _new_recipe works correctly with architectures."""
    remote_build_service._lp_project = mock_lp_project
    remote_build_service.RecipeClass = mock.Mock()
    repo = mock.Mock(git_https_url="https://localhost/~me/some-project/+git/my-repo")

    remote_build_service._new_recipe("test-recipe", repo, architectures=archs)

    remote_build_service.RecipeClass.new.assert_called_once_with(
        remote_build_service.lp,
        "test-recipe",
        "craft_test_user",
        git_ref="/~me/some-project/+git/my-repo/+ref/main",
        project="craft_test_user-craft-remote-build",
        architectures=expected_archs,
    )


def test_not_setup(remote_build_service):
    with pytest.raises(RuntimeError):
        all(remote_build_service.monitor_builds())
    with pytest.raises(RuntimeError):
        remote_build_service.fetch_logs(pathlib.Path())
    with pytest.raises(RuntimeError):
        remote_build_service.fetch_artifacts(pathlib.Path())


@pytest.mark.parametrize(
    "build_states",
    [
        [{"riscv64": launchpad.models.BuildState.SUCCESS}],
        [
            {"amd64": launchpad.models.BuildState.PENDING},
            {"amd64": launchpad.models.BuildState.PENDING},
            {"amd64": launchpad.models.BuildState.BUILDING},
            {"amd64": launchpad.models.BuildState.BUILDING},
            {"amd64": launchpad.models.BuildState.BUILDING},
            {"amd64": launchpad.models.BuildState.SUCCESS},
        ],
        [
            {
                "riscv64": launchpad.models.BuildState.SUCCESS,
                "amd64": launchpad.models.BuildState.BUILDING,
            },
            {
                "riscv64": launchpad.models.BuildState.SUCCESS,
                "amd64": launchpad.models.BuildState.BUILDING,
            },
            {
                "riscv64": launchpad.models.BuildState.SUCCESS,
                "amd64": launchpad.models.BuildState.BUILDING,
            },
            {
                "riscv64": launchpad.models.BuildState.SUCCESS,
                "amd64": launchpad.models.BuildState.BUILDING,
            },
            {
                "riscv64": launchpad.models.BuildState.SUCCESS,
                "amd64": launchpad.models.BuildState.BUILDING,
            },
            {
                "riscv64": launchpad.models.BuildState.SUCCESS,
                "amd64": launchpad.models.BuildState.SUCCESS,
            },
        ],
    ],
)
@pytest.mark.usefixtures("instant_sleep")
def test_monitor_builds_success(remote_build_service, build_states):
    remote_build_service._get_build_states = mock.Mock(side_effect=build_states)
    remote_build_service._is_setup = True

    assert list(remote_build_service.monitor_builds()) == build_states


def test_monitor_builds_timeout(remote_build_service):
    result = {"riscv64": launchpad.models.BuildState.PENDING}
    remote_build_service._get_build_states = mock.Mock(return_value=result)
    remote_build_service._is_setup = True
    remote_build_service.set_timeout(0)

    monitor_iterator = remote_build_service.monitor_builds()

    assert next(monitor_iterator) == result
    with pytest.raises(TimeoutError, match="Monitoring builds timed out."):
        next(monitor_iterator)


@pytest.mark.parametrize(
    "logs",
    [
        [],
        [{"build_log_url": "http://whatever", "arch_tag": "riscv64"}],
    ],
)
def test_fetch_logs(tmp_path, remote_build_service, logs, mocker):
    mock_datetime = mocker.patch("datetime.datetime")
    mock_datetime.now().isoformat.return_value = "2024-01-01T12:34:56"

    remote_build_service._name = "appname-project-checksum"
    remote_build_service._builds = [mock.Mock(**log) for log in logs]
    remote_build_service._is_setup = True
    remote_build_service.request = mock.Mock()

    actual = remote_build_service.fetch_logs(tmp_path)

    assert list(actual) == [item["arch_tag"] for item in logs]

    remote_build_service.request.download_files_with_progress.assert_called_once_with(
        {
            log["build_log_url"]: tmp_path
            / f"appname-project-checksum_{log['arch_tag']}_2024-01-01T12:34:56.txt"
            for log in logs
        }
    )


@pytest.mark.parametrize("architectures", [["amd64"], None])
@pytest.mark.usefixtures("mock_push_url")
def test_new_build(
    tmp_path,
    remote_build_service,
    architectures,
):
    git.GitRepo(tmp_path)
    remote_build_service.start_builds(tmp_path, architectures)
    remote_build_service.monitor_builds()
    remote_build_service.fetch_logs(tmp_path)
    remote_build_service.fetch_artifacts(tmp_path)
    remote_build_service.cleanup()


def test_new_build_not_git_repo(
    tmp_path,
    remote_build_service,
):
    with pytest.raises(RemoteBuildInvalidGitRepoError):
        remote_build_service.start_builds(tmp_path, None)


def test_credentials_filepath(app_metadata, fake_services):
    """Test that the credentials file path is correctly generated."""
    credentials_filepath = services.RemoteBuildService(
        app_metadata, fake_services
    ).credentials_filepath

    assert (
        credentials_filepath
        == platformdirs.user_data_path(app_metadata.name) / "launchpad-credentials"
    )
