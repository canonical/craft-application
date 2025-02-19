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
"""Unit tests for the ProjectService."""

import pathlib
import textwrap
from unittest import mock

import craft_platforms
import pytest

from craft_application import errors
from craft_application.application import AppMetadata
from craft_application.services.project import ProjectService


def test_resolve_file_path_success(
    project_service: ProjectService, tmp_path: pathlib.Path, app_metadata: AppMetadata
):
    project_file = tmp_path / f"{app_metadata.name}.yaml"
    project_file.touch()

    assert project_service.resolve_project_file_path() == project_file


def test_resolve_file_path_missing(
    project_service: ProjectService, tmp_path: pathlib.Path
):
    with pytest.raises(
        errors.ProjectFileMissingError,
        match=rf"Project file '[a-z]+.yaml' not found in '{tmp_path}'.",
    ):
        project_service.resolve_project_file_path()


# TODO: test load_raw_project

# TODO: test app_render_legacy_platforms


@pytest.mark.parametrize(
    ("platforms", "expected"),
    [
        pytest.param({}, {}, id="empty"),
        *(
            pytest.param(
                {str(arch): None},
                {str(arch): {"build-on": [str(arch)], "build-for": [str(arch)]}},
                id=f"expand-{arch}",
            )
            for arch in craft_platforms.DebianArchitecture
        ),
        *(
            pytest.param(
                {"anything": {"build-on": [str(arch)], "build-for": ["all"]}},
                {"anything": {"build-on": [str(arch)], "build-for": ["all"]}},
                id=f"on-{arch}-for-all",
            )
            for arch in craft_platforms.DebianArchitecture
        ),
    ],
)
def test_get_platforms(
    project_service: ProjectService,
    platforms: dict[str, dict[str, list[str] | None]],
    expected,
):
    project_service._load_raw_project = lambda: {"platforms": platforms}  # type: ignore  # noqa: PGH003

    assert project_service.get_platforms() == expected


# TODO: test get_project_vars


def test_partitions_with_partitions_disabled(project_service: ProjectService):
    assert project_service.get_partitions() is None


@pytest.mark.usefixtures("enable_partitions")
def test_default_partitions_when_enabled(project_service: ProjectService):
    assert project_service.get_partitions() == ["default"]


@pytest.mark.parametrize(
    ("project_data", "expected"),
    [
        pytest.param({}, {}, id="empty"),
        pytest.param(
            {
                "name": "my-name",
                "version": "1.2.3",
                "parts": {
                    "my-part": {
                        "plugin": "nil",
                        "source-tag": "v$CRAFT_PROJECT_VERSION",
                        "build-environment": [
                            {"BUILD_ON": "$CRAFT_ARCH_BUILD_ON"},
                        ],
                        "override-build": "echo $CRAFT_PROJECT_NAME",
                    }
                },
            },
            {
                "name": "my-name",
                "version": "1.2.3",
                "parts": {
                    "my-part": {
                        "plugin": "nil",
                        "source-tag": "v1.2.3",
                        "build-environment": [
                            {
                                "BUILD_ON": craft_platforms.DebianArchitecture.from_host().value
                            },
                        ],
                        "override-build": "echo my-name",
                    }
                },
            },
            id="basic",
        ),
    ],
)
@pytest.mark.parametrize(
    "build_for", [arch.value for arch in craft_platforms.DebianArchitecture] + ["all"]
)
def test_expand_environment_no_partitions_any_platform(
    project_service: ProjectService, project_data, build_for, expected
):
    project_service._expand_environment(project_data, build_for)
    assert project_data == expected


@pytest.mark.parametrize(
    ("project_data", "expected"),
    [
        pytest.param(
            {
                "name": "my-name",
                "version": "1.2.3",
                "parts": {
                    "my-part": {
                        "plugin": "nil",
                        "source-tag": "v$CRAFT_PROJECT_VERSION",
                        "build-environment": [
                            {"BUILD_ON": "$CRAFT_ARCH_BUILD_ON"},
                            {"BUILD_FOR": "$CRAFT_ARCH_BUILD_FOR"},
                        ],
                        "override-build": "echo $CRAFT_PROJECT_NAME",
                    }
                },
            },
            {
                "name": "my-name",
                "version": "1.2.3",
                "parts": {
                    "my-part": {
                        "plugin": "nil",
                        "source-tag": "v1.2.3",
                        "build-environment": [
                            {"BUILD_ON": mock.ANY},
                            {"BUILD_FOR": "riscv64"},
                        ],
                        "override-build": "echo my-name",
                    }
                },
            },
            id="basic",
        ),
    ],
)
def test_expand_environment_for_riscv64(
    project_service: ProjectService, project_data, expected, fake_host_architecture
):
    project_service._expand_environment(project_data, "riscv64")
    assert project_data == expected


@pytest.mark.parametrize(
    "build_for", [arch.value for arch in craft_platforms.DebianArchitecture] + ["all"]
)
@pytest.mark.usefixtures("enable_partitions")
def test_expand_environment_stage_dirs(
    project_service: ProjectService, build_for: str, tmp_path: pathlib.Path
):
    default_stage_dir = tmp_path / "stage"
    a_stage_dir = tmp_path / "partitions/a/stage"
    default_prime_dir = tmp_path / "prime"
    a_prime_dir = tmp_path / "partitions/a/prime"
    project_service.get_partitions = lambda: ["default", "a"]
    my_part = {
        "plugin": "nil",
        "override-stage": "echo $CRAFT_STAGE\necho $CRAFT_DEFAULT_STAGE\necho $CRAFT_A_STAGE",
        "override-prime": "echo $CRAFT_PRIME\necho $CRAFT_DEFAULT_PRIME\necho $CRAFT_A_PRIME",
    }
    data = {"parts": {"my-part": my_part}}
    project_service._expand_environment(data, build_for)
    assert data["parts"]["my-part"]["override-stage"] == textwrap.dedent(
        f"""\
        echo {default_stage_dir}
        echo {default_stage_dir}
        echo {a_stage_dir}"""
    )
    assert data["parts"]["my-part"]["override-prime"] == textwrap.dedent(
        f"""\
        echo {default_prime_dir}
        echo {default_prime_dir}
        echo {a_prime_dir}"""
    )


# TODO: test render_for

# TODO: test render_once

# TODO: test get
