#  This file is part of craft-application.
#
#  Copyright 2023 Canonical Ltd.
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
"""Unit tests for base service class."""
import pytest
from craft_application import errors, services


class FakeLazyService(services.BaseService):
    pass


def test_service_load_success(app_metadata, fake_services, fake_project):
    def project_getter():
        return fake_project

    service = FakeLazyService(
        app_metadata, fake_services, project_getter=project_getter
    )

    assert service._project is None
    assert service._get_project() == fake_project
    assert service._project == fake_project


def test_service_load_failure(app_metadata, fake_services):
    def project_getter():
        raise ValueError("No service for you!")

    service = FakeLazyService(
        app_metadata, fake_services, project_getter=project_getter
    )

    assert service._project is None
    with pytest.raises(errors.CraftError, match=r"^Project could not be loaded.$"):
        service._get_project()
    assert service._project is None
