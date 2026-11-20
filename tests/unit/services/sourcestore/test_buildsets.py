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
"""Unit tests for buildsets-related methods."""

from pathlib import Path
from typing import Any, cast
from unittest.mock import Mock, call

import httpx
import pytest
from craft_application.services.sourcestore import SourceStoreService
from craft_store import creds
from craft_store.models import Plane
from craft_store.publisher import Buildset

BUILDSET_ID = "bb398f21798f4c6996c56e9e27747a1b"

FAKE_LOGS = {
    "https://api.staging.charmhub.io/v1/builds/400733977bf04d2680f64a59e33dbd95/log/download": "build log for amd64",
    "https://api.staging.charmhub.io/v1/builds/400733977bf04d2680f64a59e33dbd95/fetch-service-metadata/download": "fetch service report for amd64",
    "https://api.staging.charmhub.io/v1/builds/e3868d4e626a4890a6ad45b3c44baf2b/log/download": "build log for s390x",
    "https://api.staging.charmhub.io/v1/builds/e3868d4e626a4890a6ad45b3c44baf2b/fetch-service-metadata/download": "fetch service report for s390x",
}


@pytest.fixture
def configured_service(
    source_store: SourceStoreService,
    fake_dev_token: creds.DeveloperToken,
    fake_buildset_success_json: dict[Any, Any],
    default_plane: Plane | None,
):
    buildset = Buildset.unmarshal(fake_buildset_success_json["buildsets"][0])

    # Mock the "get_buildsets" call
    get_buildsets = cast(Mock, source_store._craft_publisher_gateway.get_buildsets)
    get_buildsets.return_value = [buildset]

    # Mock the "get" call to download the actual log files
    get = cast(Mock, source_store._craft_publisher_gateway.get)
    get.side_effect = lambda url: httpx.Response(
        status_code=200,
        content=FAKE_LOGS[str(url)],
        request=httpx.Request("GET", str(url)),
    )

    yield source_store

    get_buildsets.assert_called_once_with(
        package_name="starcraft-test", buildset_id=BUILDSET_ID, plane=default_plane
    )
    assert get.mock_calls == [call(url=url) for url in FAKE_LOGS]


@pytest.mark.usefixtures("fake_dev_token")
def test_download_buildsets(
    configured_service: SourceStoreService,
    tmp_path: Path,
    default_plane: Plane | None,
):
    logs = configured_service.download_logs(
        package_name="starcraft-test",
        buildset_id=BUILDSET_ID,
        dest_dir=tmp_path,
        plane=default_plane,
    )

    def build_filename(suffix):
        return tmp_path / f"{BUILDSET_ID}-{suffix}"

    assert logs == {
        "amd64": [
            build_filename("amd64-build.txt"),
            build_filename("amd64-report.json"),
        ],
        "s390x": [
            build_filename("s390x-build.txt"),
            build_filename("s390x-report.json"),
        ],
    }

    def read_file(suffix):
        return build_filename(suffix).read_text()

    # Check that all 4 files were downloaded: build log and fetch-service report, for
    # both amd64 and s390x.
    assert read_file("amd64-build.txt") == "build log for amd64"
    assert read_file("amd64-report.json") == "fetch service report for amd64"
    assert read_file("s390x-build.txt") == "build log for s390x"
    assert read_file("s390x-report.json") == "fetch service report for s390x"
