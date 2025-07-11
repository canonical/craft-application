# This file is part of craft_application.
#
# Copyright 2023 Canonical Ltd.
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
"""Configuration for craft-application unit tests."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest import mock

import pytest

if TYPE_CHECKING:
    import pytest_mock

from craft_application import git, services
from craft_application.services import service_factory


@pytest.fixture
def project_service(
    app_metadata, fake_services, project_path, fake_project_service_class
):
    fake_services.register("project", fake_project_service_class)
    return fake_project_service_class(
        app_metadata,
        fake_services,
        project_dir=project_path,
    )


@pytest.fixture
def provider_service(app_metadata, fake_project, fake_services, tmp_path):
    return services.ProviderService(
        app_metadata,
        fake_services,
        work_dir=tmp_path,
    )


@pytest.fixture
def mock_services(monkeypatch, app_metadata, fake_project, project_path):
    mock_config = mock.Mock(spec=services.ConfigService)
    mock_config.return_value.get.return_value = None
    services.ServiceFactory.register("config", mock_config)
    services.ServiceFactory.register("fetch", mock.Mock(spec=services.FetchService))
    services.ServiceFactory.register("init", mock.MagicMock(spec=services.InitService))
    services.ServiceFactory.register(
        "lifecycle", mock.Mock(spec=services.LifecycleService)
    )
    services.ServiceFactory.register("package", mock.Mock(spec=services.PackageService))
    services.ServiceFactory.register(
        "provider", mock.Mock(spec=services.ProviderService)
    )
    services.ServiceFactory.register(
        "remote_build", mock.Mock(spec=services.RemoteBuildService)
    )
    services.ServiceFactory.register("testing", mock.Mock(spec=services.TestingService))

    def forgiving_is_subclass(child, parent):
        if not isinstance(child, type):
            return False
        return issubclass(child, parent)

    # Mock out issubclass on the service factory since we're registering mock objects
    # rather than actual classes.
    monkeypatch.setattr(
        service_factory, "issubclass", forgiving_is_subclass, raising=False
    )
    factory = services.ServiceFactory(app_metadata, project=fake_project)
    factory.update_kwargs("project", project_dir=project_path)
    return factory


@pytest.fixture
def clear_git_binary_name_cache() -> None:
    git.GitRepo.get_git_command.cache_clear()


@pytest.fixture(
    params=[
        pytest.param(True, id="craftgit_available"),
        pytest.param(False, id="fallback_to_git"),
    ],
)
def expected_git_command(
    request: pytest.FixtureRequest,
    mocker: pytest_mock.MockerFixture,
    clear_git_binary_name_cache: None,
) -> str:
    craftgit_exists = request.param
    which_res = f"/some/path/to/{git.CRAFTGIT_BINARY_NAME}" if craftgit_exists else None
    mocker.patch("shutil.which", return_value=which_res)
    return git.CRAFTGIT_BINARY_NAME if craftgit_exists else git.GIT_FALLBACK_BINARY_NAME
