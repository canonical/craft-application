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
import pytest_check


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


@pytest.mark.parametrize(
    "files",
    [
        {
            "https://github.com/canonical/craft-application/archive/refs/tags/1.2.1.tar.gz": "416db371643cc7a40efc5b5ca180c021e43025af7f73e93de82a4a0900121b99",
            "https://github.com/canonical/craft-application/archive/refs/tags/1.2.1.zip": "4d6128bbf388009e80e27644eccc2393246eece745c6989374b693a5c5eaca9c",
            "https://github.com/canonical/craft-application/archive/refs/tags/1.2.0.tar.gz": "5239d8e3402b4cef5fe7e8bd31fa507caa3ae62640d4309561ef12d1d2770e34",
            "https://github.com/canonical/craft-application/archive/refs/tags/1.2.0.zip": "369a2fc5abb6593e6d677495af49cbf0b4fb25ad10973ffb3250f0c66cd7c570",
            "https://github.com/canonical/craft-application/archive/refs/tags/1.1.0.tar.gz": "b70e4185b9b1b82a81dad968b97bc88f788f8112aa5271df0dbbd75121921acb",
            "https://github.com/canonical/craft-application/archive/refs/tags/1.1.0.zip": "42eb28a319ba256f92df968b5978337e7cd0201beeb801f38c90766fd880ed47",
            "https://github.com/canonical/craft-application/archive/refs/tags/1.0.0.tar.gz": "d731ab49e654a131d092529c2e5e023852819991df692a9297aafbb845325461",
            "https://github.com/canonical/craft-application/archive/refs/tags/1.0.0.zip": "6f8204619669fe62ef4e6724ab4e2c8cbc05c874a38df9f8be30f98b0a487036",
        },
    ],
)
def test_get_real_files(tmp_path, request_service, files):
    result = request_service.download_files_with_progress({f: tmp_path for f in files})

    for url, path in result.items():
        expected_hash = files[url]
        actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()

        pytest_check.equal(actual_hash, expected_hash, url)
