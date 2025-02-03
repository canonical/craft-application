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

from unittest import mock

import pytest
import pytest_mock

from craft_application import git, services, util
from craft_application.services import service_factory


@pytest.fixture(params=["amd64", "arm64", "riscv64"])
def fake_host_architecture(monkeypatch, request) -> str:
    monkeypatch.setattr(util, "get_host_architecture", lambda: request.param)
    return request.param


@pytest.fixture
def provider_service(
    app_metadata, fake_project, fake_build_plan, fake_services, tmp_path
):
    return services.ProviderService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=tmp_path,
        build_plan=fake_build_plan,
    )


@pytest.fixture
def mock_services(monkeypatch, app_metadata, fake_project):
    services.ServiceFactory.register("config", mock.Mock(spec=services.ConfigService))
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

    def forgiving_is_subclass(child, parent):
        if not isinstance(child, type):
            return False
        return issubclass(child, parent)

    # Mock out issubclass on the service factory since we're registering mock objects
    # rather than actual classes.
    monkeypatch.setattr(
        service_factory, "issubclass", forgiving_is_subclass, raising=False
    )
    return services.ServiceFactory(app_metadata, project=fake_project)


@pytest.fixture
def clear_git_binary_name_cache() -> None:
    from craft_application.git import GitRepo

    GitRepo.get_git_command.cache_clear()


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
