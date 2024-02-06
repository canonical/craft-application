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
"""Integration tests for the Request service."""
import hashlib
from unittest.mock import call

import pytest


@pytest.mark.parametrize(
    ("url", "checksum", "size"),
    [
        pytest.param(
            # A real build log.
            "https://launchpad.net/~charmcraft-team/charmcraft/+snap/charmcraft-edge/+build/2377699/+files/buildlog_snap_ubuntu_jammy_armhf_charmcraft-edge_BUILDING.txt.gz",
            # The hash of the plain text file (uncompressed)
            "1f3b5ac763cf6885c26965f8d559bca6e8a6b2d2b2ce1f8935628647f57a0c0a",
            29595,  # Size of the compressed file.
            id="real-logfile",
        )
    ],
)
def test_get_real_file(tmp_path, emitter, request_service, url, checksum, size):
    result = request_service.download_with_progress(url, tmp_path)
    actual_hash = hashlib.sha256(result.read_bytes()).hexdigest()

    assert actual_hash == checksum
    emitter.assert_interactions(
        [
            call("progress_bar", f"Downloading {url}", size),
        ]
    )
