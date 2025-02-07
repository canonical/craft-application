# This file is part of craft-application.
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
"""Tests for remote-build commands."""

import argparse

import pytest
from craft_cli import emit

from craft_application.commands import RemoteBuild
from craft_application.errors import RemoteBuildError
from craft_application.launchpad.models import BuildState
from craft_application.services import RemoteBuildService


@pytest.fixture
def remote_build(
    app_metadata,
    fake_services,
):
    config = {"app": app_metadata, "services": fake_services}
    return RemoteBuild(config)


def test_remote_build_run(remote_build, mocker, fake_services, tmp_path, emitter):
    builder = fake_services.remote_build

    build_states = [
        # All 4 builds still pending
        {
            "arch1": BuildState.PENDING,
            "arch2": BuildState.PENDING,
            "arch3": BuildState.PENDING,
            "arch4": BuildState.PENDING,
        },
        # 2 builds running, 2 pending
        {
            "arch1": BuildState.BUILDING,
            "arch2": BuildState.BUILDING,
            "arch3": BuildState.PENDING,
            "arch4": BuildState.PENDING,
        },
        # 1 uploading, 1 building, 1 pending, 1 stopped
        {
            "arch1": BuildState.UPLOADING,
            "arch2": BuildState.BUILDING,
            "arch3": BuildState.PENDING,
            "arch4": BuildState.SUPERSEDED,
        },
        # 3 succeeded, 1 stopped
        {
            "arch1": BuildState.SUCCESS,
            "arch2": BuildState.SUCCESS,
            "arch3": BuildState.SUCCESS,
            "arch4": BuildState.SUPERSEDED,
        },
    ]

    mocker.patch.object(
        builder, "start_builds", return_value=["arch1", "arch2", "arch3", "arch4"]
    )
    mocker.patch.object(builder, "monitor_builds", side_effect=[build_states])

    logs = {
        "arch1": tmp_path / "log1.txt",
        "arch2": tmp_path / "log2.txt",
        "arch3": tmp_path / "log3.txt",
        "arch4": tmp_path / "log4.txt",
    }
    mocker.patch.object(builder, "fetch_logs", return_value=logs)

    artifacts = [
        tmp_path / "art1.zip",
        tmp_path / "art2.zip",
        tmp_path / "art3.zip",
        tmp_path / "art4.zip",
    ]
    mocker.patch.object(builder, "fetch_artifacts", return_value=artifacts)

    parsed_args = argparse.Namespace(
        launchpad_accept_public_upload=True,
        launchpad_timeout=None,
        recover=False,
        project=None,
    )
    assert remote_build.run(parsed_args) is None

    emitter.assert_progress(
        "Starting new build. It may take a while to upload large projects."
    )
    emitter.assert_progress("Pending: arch1, arch2, arch3, arch4")
    emitter.assert_progress("Building: arch1, arch2; Pending: arch3, arch4")
    emitter.assert_progress(
        "Stopped: arch4; Building: arch2; Uploading: arch1; Pending: arch3"
    )
    emitter.assert_progress("Stopped: arch4; Succeeded: arch1, arch2, arch3")
    emitter.assert_progress("Fetching 4 build logs...")
    emitter.assert_progress("Fetching build artifacts...")
    emitter.assert_message(
        "Build completed.\n"
        "Log files: log1.txt, log2.txt, log3.txt, log4.txt\n"
        "Artifacts: art1.zip, art2.zip, art3.zip, art4.zip"
    )


@pytest.mark.parametrize(
    ("accept_public", "is_private", "project", "confirm"),
    [
        pytest.param(True, False, None, False, id="accepted-public"),
        pytest.param(False, False, None, True, id="accepted-cli"),
        pytest.param(False, True, "my-project", False, id="named-priv-proj"),
    ],
)
def test_set_project_succeeds(
    mocker,
    remote_build: RemoteBuild,
    accept_public: bool,
    is_private: bool,
    project: str | None,
    confirm: bool,
) -> None:
    # Remote build should succeed if any of the following were done:
    # - The `--launchpad-accept-public-upload` flag was used
    # - The project has been specified and happens to be private
    # - The user confirms from CLI that they accept public uploads
    mocker.patch.object(
        RemoteBuildService, "is_project_private", return_value=is_private
    )
    mocker.patch.object(emit, "confirm", return_value=confirm)
    parsed_args = argparse.Namespace(
        launchpad_accept_public_upload=accept_public,
        project=project,
        launchpad_timeout=0,
        recover=False,
    )

    # Don't actually start a build
    mocker.patch.object(RemoteBuildService, "start_builds", return_value=[])
    mocker.patch.object(RemoteBuild, "_monitor_and_complete", return_value=0)
    assert remote_build.run(parsed_args) is None


@pytest.mark.parametrize(
    ("is_private", "project"),
    [
        pytest.param(False, None, id="no-positives"),
        pytest.param(False, "my_project", id="named-proj"),
        pytest.param(True, None, id="is_private"),
    ],
)
def test_set_project_failures(
    mocker, remote_build: RemoteBuild, is_private: bool, project: str | None
) -> None:
    # Remote build should fail if there is no confirmation and either:
    # - Project is public
    # - No project name was specified
    # - Both of the above
    mocker.patch.object(
        RemoteBuildService, "is_project_private", return_value=is_private
    )
    mocker.patch.object(emit, "confirm", return_value=False)
    parsed_args = argparse.Namespace(
        launchpad_accept_public_upload=False, project=project
    )

    with pytest.raises(RemoteBuildError) as exc:
        remote_build.run(parsed_args)

    assert exc.value.retcode == 77
