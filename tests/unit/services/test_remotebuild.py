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

import lazr.restfulclient.errors
import lazr.restfulclient.resource
import pytest
from craft_application import launchpad
from craft_application.remote import git

from tests.unit.services.conftest import (
    get_mock_callable,
)


@pytest.fixture()
def mock_push_url(monkeypatch):
    push_url = get_mock_callable(return_value=None)
    monkeypatch.setattr(git.GitRepo, "push_url", push_url)
    return push_url


@pytest.fixture()
def mock_lp_project(fake_launchpad, mock_project_entry):
    return launchpad.models.Project(fake_launchpad, mock_project_entry)


def test_ensure_project_existing(remote_build_service, mock_project_entry):
    remote_build_service.lp.lp.projects = {
        "craft_test_user-craft-remote-build": mock_project_entry
    }

    remote_build_service._ensure_project()


def test_ensure_project_new(remote_build_service):
    remote_build_service.lp.lp.projects.__getitem__.side_effect = (
        lazr.restfulclient.errors.NotFound("yo", "dawg")
    )

    remote_build_service._ensure_project()


def test_new_repository(
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

    work_tree, lp_repository = remote_build_service._new_repository(tmp_path)

    assert (work_tree.repo_dir / "sentinel_file").read_text() == sentinel.read_text()
    mock_push_url.assert_called_once_with(
        "https://craft_test_user:super_secret_token@git.launchpad.net/~user/+git/my_repo",
        "main",
    )
    expiry = wrapped_repository.get_access_token.call_args.kwargs["expiry"]

    # Ensure that we're getting a timezone-aware object in the method.
    # This is here as a regression test because if you're in a timezone behind UTC
    # the expiry time sent to Launchpad will have already expired and Launchpad
    # does not catch that. So instead we make sure thot even when using the easternmost
    # time zone the expiry time is still in the future.
    tz = datetime.timezone(datetime.timedelta(hours=14))
    assert expiry > datetime.datetime.now(tz=tz)


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
def test_fetch_logs(tmp_path, remote_build_service, logs):
    remote_build_service._name = "appname-project-checksum"
    remote_build_service._builds = [mock.Mock(**log) for log in logs]
    remote_build_service._is_setup = True
    remote_build_service.request = mock.Mock()

    actual = remote_build_service.fetch_logs(tmp_path)

    assert list(actual) == [item["arch_tag"] for item in logs]

    remote_build_service.request.download_files_with_progress.assert_called_once_with(
        {log["build_log_url"]: mock.ANY for log in logs}
    )


@pytest.mark.parametrize("architectures", [["amd64"], None])
@pytest.mark.usefixtures("mock_push_url")
def test_new_build(
    tmp_path,
    remote_build_service,
    architectures,
):
    remote_build_service.start_builds(tmp_path, architectures)
    remote_build_service.monitor_builds()
    remote_build_service.fetch_logs(tmp_path)
    remote_build_service.fetch_artifacts(tmp_path)
    remote_build_service.cleanup()
