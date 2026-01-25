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


@responses.activate
def test_download_chunks_with_chunked_encoding_error_retry(
    tmp_path, emitter, request_service
):
    """Test that download_chunks retries on ChunkedEncodingError and eventually succeeds.

    This test simulates a ChunkedEncodingError occurring during download.iter_content(),
    verifies that the download is retried, and ensures the final download completes
    successfully with the correct data and chunk count (not counting failed attempts).
    """
    data = b"This is test data for download retry"
    output_file = tmp_path / "file"

    # Patch the get method to simulate ChunkedEncodingError on first attempts
    original_get = request_service.get
    call_count = {"count": 0}

    # Set up the mock response
    responses.add(
        responses.GET,
        "http://example/file",
        body=data,
        headers={"Content-Length": str(len(data))},
    )

    def patched_get(*args, **kwargs):
        call_count["count"] += 1
        response = original_get(*args, **kwargs)

        # Make iter_content raise ChunkedEncodingError on first two attempts
        if call_count["count"] <= 2:

            def failing_iter_content(chunk_size):
                # Yield some data first to simulate partial download
                yield b"partial"
                # Then raise the error
                raise requests.exceptions.ChunkedEncodingError(
                    "Connection broken: Invalid chunk encoding"
                )

            response.iter_content = failing_iter_content

        return response

    with patch.object(request_service, "get", side_effect=patched_get):
        downloader = request_service.download_chunks("http://example/file", output_file)
        size = next(downloader)
        dl_size = sum(downloader)

    # Verify that the download eventually succeeded
    pytest_check.equal(int(size), len(data), "Downloaded size is incorrect")
    pytest_check.equal(dl_size, len(data), "Downloaded size is incorrect")
    pytest_check.equal(output_file.read_bytes(), data, "Download data is incorrect")

    # Verify that retry messages were emitted
    progress_calls = [
        interaction
        for interaction in emitter.interactions
        if len(interaction.args) > 0
        and interaction.args[0] == "progress"
        and len(interaction.args) > 1
        and "retrying" in interaction.args[1]
    ]
    pytest_check.equal(len(progress_calls), 2, "Expected 2 retry progress messages")

    # Verify that we made 3 attempts (2 failures + 1 success)
    pytest_check.equal(call_count["count"], 3, "Expected 3 download attempts")


@responses.activate
def test_download_chunks_chunked_encoding_error_exhausted(tmp_path, request_service):
    """Test that download_chunks raises ChunkedEncodingError after max retries.

    This test simulates a persistent ChunkedEncodingError that occurs on every
    download attempt, and verifies that after exhausting all retry attempts,
    the error is properly raised to the caller.
    """
    data = b"test data"
    output_file = tmp_path / "file"

    # Set up the mock response
    responses.add(
        responses.GET,
        "http://example/file",
        body=data,
        headers={"Content-Length": str(len(data))},
    )

    # Patch to always fail
    original_get = request_service.get

    def patched_get(*args, **kwargs):
        response = original_get(*args, **kwargs)

        def failing_iter_content(chunk_size):
            # Yield some data first
            yield b"partial"
            # Then raise the error
            raise requests.exceptions.ChunkedEncodingError(
                "Connection broken: Invalid chunk encoding"
            )

        response.iter_content = failing_iter_content
        return response

    with patch.object(request_service, "get", side_effect=patched_get):
        downloader = request_service.download_chunks("http://example/file", output_file)
        next(downloader)  # Get the size

        # The error should be raised after max_retries attempts
        with pytest.raises(requests.exceptions.ChunkedEncodingError):
            list(downloader)  # Consume the iterator
