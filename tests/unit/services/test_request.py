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
"""Unit tests for the Request service."""
from unittest.mock import call

import craft_cli.pytest_plugin
import pytest
import pytest_check
import responses
from hypothesis import HealthCheck, given, settings, strategies


@responses.activate
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(data=strategies.binary())
def test_download_chunks(tmp_path, request_service, data):
    responses.add(
        responses.GET,
        "http://example/file",
        body=data,
        headers={"Content-Length": str(len(data))},
    )
    output_file = tmp_path / "file"

    downloader = request_service.download_chunks("http://example/file", output_file)
    size = next(downloader)
    dl_size = sum(downloader)

    pytest_check.equal(int(size), len(data), "Downloaded size is incorrect")
    pytest_check.equal(dl_size, len(data), "Downloaded size is incorrect")
    pytest_check.equal(output_file.read_bytes(), data, "Download data is incorrect")

    downloader = request_service.download_chunks("http://example/file", tmp_path)
    size = next(downloader)
    dl_size = sum(downloader)

    pytest_check.equal(int(size), len(data), "Downloaded size is incorrect")
    pytest_check.equal(dl_size, len(data), "Downloaded size is incorrect")
    pytest_check.equal(output_file.read_bytes(), data, "Download data is incorrect")


@responses.activate
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(data=strategies.binary(min_size=1))
def test_download_with_progress(
    tmp_path, emitter: craft_cli.pytest_plugin.RecordingEmitter, request_service, data
):
    emitter.interactions = []  # Reset the emitter so we can re-run with hypothesis.
    responses.add(
        responses.GET,
        "http://example/file",
        body=data,
        headers={"Content-Length": str(len(data))},
    )
    output_file = tmp_path / "file"

    request_service.download_with_progress("http://example/file", tmp_path)

    pytest_check.equal(output_file.read_bytes(), data, "Download data is incorrect")
    emitter.assert_interactions(
        [
            call("progress_bar", "Downloading http://example/file", len(data)),
            call("advance", len(data)),
        ]
    )


@responses.activate
@pytest.mark.parametrize(
    "downloads",
    [
        {
            "http://example/empty.txt": b"",
            "http://example/file": b"abc",
            "https://localhost/file.py": b"#!/usr/bin/env python3\nprint('hi')",
        },
    ],
)
def test_download_files_with_progress(tmp_path, emitter, request_service, downloads):
    files = {url: tmp_path for url in downloads}
    for url, data in downloads.items():
        responses.add(
            responses.GET, url, body=data, headers={"Content-Length": str(len(data))}
        )

    results = request_service.download_files_with_progress(files)

    assert emitter.interactions[0] == call(
        "progress_bar",
        f"Downloading {len(downloads)} files",
        sum(len(dl) for dl in downloads.values()),
    )
    for file in downloads.values():
        if len(file) > 0:  # Advance doesn't get called on empty files
            assert call("advance", len(file)) in emitter.interactions

    for url, path in results.items():
        assert path.read_bytes() == downloads[url]
