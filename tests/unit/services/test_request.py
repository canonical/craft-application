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

from unittest.mock import call, patch

import craft_cli.pytest_plugin
import pytest
import pytest_check
import requests
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
            call(
                "debug",
                "Trying to download http://example/file (attempt 1/6)",
            ),
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
    files = dict.fromkeys(downloads, tmp_path)
    for url, data in downloads.items():
        responses.add(
            responses.GET, url, body=data, headers={"Content-Length": str(len(data))}
        )

    results = request_service.download_files_with_progress(files)

    emitter.assert_interactions(
        [
            call(
                "progress_bar",
                f"Downloading {len(downloads)} files",
                sum(len(dl) for dl in downloads.values()),
            )
        ]
    )
    for file in downloads.values():
        if len(file) > 0:  # Advance doesn't get called on empty files
            assert call("advance", len(file)) in emitter.interactions

    for url, path in results.items():
        assert path.read_bytes() == downloads[url]


def iter_content_then_raise_chunked_encoding_error(
    chunk_size=None,  # pylint: disable=unused-argument
):
    """Yield partial data, then simulate an interrupted response."""
    yield b"partial"
    raise requests.exceptions.ChunkedEncodingError(
        "Connection broken: Invalid chunk encoding"
    )


@responses.activate
def test_download_with_progress_retries_chunked_encoding_error(
    tmp_path, emitter, mocker, request_service
):
    """Retry an interrupted download and roll back its partial progress."""
    data = b"This is test data for download retry"
    output_file = tmp_path / "file"
    original_get = request_service.get
    attempts = 0
    mocked_sleep = mocker.patch("time.sleep")

    responses.add(
        responses.GET,
        "http://example/file",
        body=data,
        headers={"Content-Length": str(len(data))},
    )

    def patched_get(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        response = original_get(*args, **kwargs)

        if attempts <= 2:
            response.iter_content = iter_content_then_raise_chunked_encoding_error

        return response

    with patch.object(request_service, "get", side_effect=patched_get):
        result = request_service.download_with_progress(
            "http://example/file", output_file
        )

    assert result == output_file
    assert output_file.read_bytes() == data
    assert attempts == 3
    assert mocked_sleep.mock_calls == [call(2), call(4)]
    assert [
        interaction
        for interaction in emitter.interactions
        if interaction.args[0] == "advance"
    ] == [
        call("advance", len(b"partial")),
        call("advance", -len(b"partial")),
        call("advance", len(b"partial")),
        call("advance", -len(b"partial")),
        call("advance", len(data)),
    ]


@responses.activate
def test_download_with_progress_exhausts_chunked_encoding_error_retries(
    tmp_path, emitter, mocker, request_service
):
    """Propagate ChunkedEncodingError after all retry attempts fail."""
    data = b"test data"
    output_file = tmp_path / "file"
    original_get = request_service.get
    attempts = 0
    mocked_sleep = mocker.patch("time.sleep")

    responses.add(
        responses.GET,
        "http://example/file",
        body=data,
        headers={"Content-Length": str(len(data))},
    )

    def patched_get(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        response = original_get(*args, **kwargs)
        response.iter_content = iter_content_then_raise_chunked_encoding_error
        return response

    with patch.object(request_service, "get", side_effect=patched_get):
        with pytest.raises(requests.exceptions.ChunkedEncodingError):
            request_service.download_with_progress("http://example/file", output_file)

    assert attempts == 6
    assert mocked_sleep.mock_calls == [call(2), call(4), call(8), call(16), call(32)]
    assert output_file.read_bytes() == b"partial"
    assert [
        interaction
        for interaction in emitter.interactions
        if interaction.args[0] == "advance"
    ] == [
        call("advance", len(b"partial")),
        call("advance", -len(b"partial")),
    ] * 6


@responses.activate
def test_download_files_with_progress_retries_only_interrupted_file(
    tmp_path, emitter, mocker, request_service
):
    """Do not repeat successful downloads when another download is retried."""
    stable_data = b"stable data"
    flaky_data = b"eventual data"
    stable_url = "http://example/stable"
    flaky_url = "http://example/flaky"
    files = {
        stable_url: tmp_path / "stable",
        flaky_url: tmp_path / "flaky",
    }
    attempts = {stable_url: 0, flaky_url: 0}
    original_get = request_service.get
    mocked_sleep = mocker.patch("time.sleep")

    responses.add(
        responses.GET,
        stable_url,
        body=stable_data,
        headers={"Content-Length": str(len(stable_data))},
    )
    responses.add(
        responses.GET,
        flaky_url,
        body=flaky_data,
        headers={"Content-Length": str(len(flaky_data))},
    )

    def patched_get(url, *args, **kwargs):
        attempts[url] += 1
        response = original_get(url, *args, **kwargs)
        if url == flaky_url and attempts[url] == 1:
            response.iter_content = iter_content_then_raise_chunked_encoding_error
        return response

    with patch.object(request_service, "get", side_effect=patched_get):
        result = request_service.download_files_with_progress(files)

    assert result == files
    assert files[stable_url].read_bytes() == stable_data
    assert files[flaky_url].read_bytes() == flaky_data
    assert attempts == {stable_url: 1, flaky_url: 2}
    assert mocked_sleep.mock_calls == [call(2)]
    assert (
        call("progress_bar", "Downloading 2 files", len(stable_data) + len(flaky_data))
        in emitter.interactions
    )
