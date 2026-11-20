# This file is part of craft-application.
#
# Copyright 2026 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Shared fixtures for sourcestore tests."""

from __future__ import annotations

import json
import pathlib
from typing import Any, cast
from unittest.mock import Mock

import pytest
from craft_application import services
from craft_application.services.sourcestore import SourceStoreService
from craft_store import creds
from craft_store.models import Plane
from craft_store.publisher import (
    ORIGIN_REMOTE_NAME,
    STORE_REMOTE_NAME,
    UPSTREAM_REMOTE_NAME,
    PublisherGateway,
    Remote,
)


@pytest.fixture
def fake_sourcestore_service_class():
    class FakeSourceStoreService(SourceStoreService):
        def __init__(
            self,
            app: services.AppMetadata,
            services: services.ServiceFactory,
        ) -> None:
            super().__init__(app, services, ephemeral_credential_storage=True)
            self._craft_publisher_gateway = Mock(spec=PublisherGateway)

    return FakeSourceStoreService


@pytest.fixture(autouse=True)
def _register_source_store(fake_sourcestore_service_class):
    services.ServiceFactory.register("source_store", fake_sourcestore_service_class)


@pytest.fixture
def source_store(
    fake_services: services.ServiceFactory, fake_sourcestore_service_class
) -> SourceStoreService:
    services.ServiceFactory.register("source_store", fake_sourcestore_service_class)
    return cast(SourceStoreService, fake_services.get("source_store"))


@pytest.fixture
def craft_publisher_gw_client_mock(source_store: SourceStoreService) -> Mock:
    return cast(Mock, source_store._craft_publisher_gateway)


def get_fake_remote(
    name: str,
    url: str,
    remote_type: str = "external",
    plane_name: str = "test-plane",
    domain_name: str = "test-domain",
    package_id="test-package-id",
    package_name="test-package",
    package_type="testcraft",
) -> Remote:
    return Remote(
        name=name,
        remote_type=remote_type,  # ty: ignore[invalid-argument-type]
        url=url,
        plane_name=plane_name,
        domain_name=domain_name,
        package_id=package_id,
        package_name=package_name,
        package_type=package_type,
    )


@pytest.fixture
def fake_origin() -> Remote:
    return get_fake_remote(
        name=ORIGIN_REMOTE_NAME,
        remote_type="external",
        url=f"https://{ORIGIN_REMOTE_NAME}.testcraft.localhost",
    )


@pytest.fixture
def fake_store() -> Remote:
    return get_fake_remote(
        name=STORE_REMOTE_NAME,
        remote_type="store",
        url=f"https://{STORE_REMOTE_NAME}.testcraft.localhost",
    )


@pytest.fixture
def fake_upstream() -> Remote:
    return get_fake_remote(
        name=UPSTREAM_REMOTE_NAME,
        remote_type="external",
        url=f"https://{UPSTREAM_REMOTE_NAME}.testcraft.localhost",
    )


@pytest.fixture
def fake_dev_token(
    source_store: SourceStoreService,
) -> creds.DeveloperToken:
    dev_token = creds.DeveloperToken(macaroon="craft-macaroon")
    source_store._credential_storage.set_credentials(dev_token.model_dump_json())
    return dev_token


@pytest.fixture(params=["craft/public", None], ids=["public_plane", "no_plane"])
def default_plane(request: pytest.FixtureRequest) -> Plane | None:
    if plane := request.param:
        plane = Plane.from_str(plane)
    return cast(Plane | None, plane)


@pytest.fixture
def empty_project_dir(tmp_path: pathlib.Path) -> pathlib.Path:
    project_dir = tmp_path / "test-project"
    project_dir.mkdir()
    return project_dir


@pytest.fixture
def project_yaml_filename() -> str:
    return "testcraft.yaml"


@pytest.fixture
def project_yaml_path(
    empty_project_dir: pathlib.Path, project_yaml_filename: str
) -> pathlib.Path:
    return empty_project_dir / project_yaml_filename


@pytest.fixture
def buildset_data_dir() -> pathlib.Path:
    return pathlib.Path(__file__).parent.parent.parent.parent / "data" / "buildset"


@pytest.fixture
def fake_buildset_success_json(buildset_data_dir) -> dict[str, Any]:
    contents = (buildset_data_dir / "response-success.json").read_text()
    return json.loads(contents)
