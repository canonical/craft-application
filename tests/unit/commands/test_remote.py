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
from craft_application.launchpad.models import BuildState


@pytest.fixture
def remote_build(
    app_metadata,
    fake_services,
):
    config = {"app": app_metadata, "services": fake_services}
    return RemoteBuild(config)


def test_remote_build_no_accept_upload(remote_build, mocker):
    parsed_args = argparse.Namespace(launchpad_accept_public_upload=False)

    mocker.patch.object(emit, "confirm", return_value=False)
    assert remote_build.run(parsed_args) == 77


def test_remote_build_run(remote_build, mocker, fake_services, tmp_path, emitter):
    builder = fake_services.remote_build

    build_states = [
        # All 3 builds still pending
        {
            "arch1": BuildState.PENDING,
            "arch2": BuildState.PENDING,
            "arch3": BuildState.PENDING,
        },
        # 2 builds running, 1 pending
        {
            "arch1": BuildState.BUILDING,
            "arch2": BuildState.BUILDING,
            "arch3": BuildState.PENDING,
        },
        # 1 uploading, 1 building, 1 pending
        {
            "arch1": BuildState.UPLOADING,
            "arch2": BuildState.BUILDING,
            "arch3": BuildState.PENDING,
        },
        # All 3 succeeded
        {
            "arch1": BuildState.SUCCESS,
            "arch2": BuildState.SUCCESS,
            "arch3": BuildState.SUCCESS,
        },
    ]

    mocker.patch.object(
        builder, "start_builds", return_value=["arch1", "arch2", "arch3"]
    )
    mocker.patch.object(builder, "monitor_builds", side_effect=[build_states])

    logs = {
        "arch1": tmp_path / "log1.txt",
        "arch2": tmp_path / "log2.txt",
        "arch3": tmp_path / "log3.txt",
    }
    mocker.patch.object(builder, "fetch_logs", return_value=logs)

    artifacts = [tmp_path / "art1.zip", tmp_path / "art2.zip", tmp_path / "art3.zip"]
    mocker.patch.object(builder, "fetch_artifacts", return_value=artifacts)

    parsed_args = argparse.Namespace(
        launchpad_accept_public_upload=True, launchpad_timeout=None, recover=False
    )
    assert remote_build.run(parsed_args) is None

    emitter.assert_progress(
        "Starting new build. It may take a while to upload large projects."
    )
    emitter.assert_progress("Stopped: arch1, arch2, arch3")
    emitter.assert_progress("Stopped: arch3; Building: arch1, arch2")
    emitter.assert_progress("Stopped: arch3; Building: arch2; Uploading: arch1")
    emitter.assert_progress("Succeeded: arch1, arch2, arch3")
    emitter.assert_progress("Fetching 3 build logs...")
    emitter.assert_progress("Fetching build artifacts...")
    emitter.assert_message(
        "Build completed.\n"
        "Log files: log1.txt, log2.txt, log3.txt\n"
        "Artifacts: art1.zip, art2.zip, art3.zip"
    )
