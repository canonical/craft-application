# Copyright 2025 Canonical Ltd.
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
"""Integration tests for checking valid project schemas."""

import pathlib

import jsonschema
import pytest
from craft_application import models, util
from craft_application.errors import CraftValidationError
from craft_application.models.platforms import Platform
from craft_application.services.project import ProjectService
from craft_application.services.service_factory import ServiceFactory

VALID_SCHEMAS_DIR = pathlib.Path(__file__).parent / "valid_testcraft"
INVALID_SCHEMAS_DIR = pathlib.Path(__file__).parent / "invalid_testcraft"


@pytest.fixture
def project_service(app_metadata, fake_services, in_project_path: pathlib.Path):
    return ProjectService(
        app=app_metadata, services=fake_services, project_dir=in_project_path
    )


@pytest.mark.parametrize(
    "fake_project_yaml",
    [
        pytest.param(path.read_text(), id=path.name)
        for path in VALID_SCHEMAS_DIR.glob("*.yaml")
    ],
)
def test_valid_testcraft_projects(
    fake_package_service_class,
    app_metadata,
    in_project_path,
    fake_project_yaml: str,
    fake_project_file: pathlib.Path,
):
    ServiceFactory.register("package", fake_package_service_class)
    project_service = ProjectService(
        app=app_metadata,
        services=ServiceFactory(app_metadata),
        project_dir=in_project_path,
    )
    schema = models.Project.model_json_schema()
    validator = jsonschema.Draft202012Validator(schema)

    # Test that it's valid according to the schema.
    validator.validate(util.safe_yaml_load(fake_project_yaml))

    # Test that we can load it with the ProjectService
    project_service.configure(platform=None, build_for=None)
    project = project_service.get()

    # Ensure that our resulting PlatformsDict is a normal dictionary.
    assert isinstance(project.platforms, dict)
    for name, platform in project.platforms.items():
        assert isinstance(name, str)
        assert isinstance(platform, Platform)


@pytest.mark.parametrize(
    "project_yaml",
    [
        pytest.param(path.read_text(), id=path.name)
        for path in INVALID_SCHEMAS_DIR.glob("*.yaml")
    ],
)
def test_invalid_testcraft_projects(
    app_metadata,
    in_project_path,
    project_yaml: str,
    fake_project_file: pathlib.Path,
    fake_package_service_class,
):
    fake_project_file.write_text(project_yaml)
    schema = models.Project.model_json_schema()
    validator = jsonschema.Draft202012Validator(schema)

    with pytest.raises(jsonschema.ValidationError):
        validator.validate(util.safe_yaml_load(project_yaml))

    ServiceFactory.register("package", fake_package_service_class)
    project_service = ProjectService(
        app=app_metadata,
        services=ServiceFactory(app_metadata),
        project_dir=in_project_path,
    )
    with pytest.raises(CraftValidationError):  # noqa: PT012
        project_service.configure(platform=None, build_for=None)
        project_service.get()
