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

import dataclasses
import pathlib
import textwrap
from typing import cast
from unittest import mock

import craft_platforms
import pydantic
import pytest
import pytest_mock
from hypothesis import given, strategies

from craft_application import errors
from craft_application.application import AppMetadata
from craft_application.services.project import ProjectService
from craft_application.services.service_factory import ServiceFactory


@pytest.fixture
def real_project_service(fake_services: ServiceFactory):
    fake_services.register("project", ProjectService)
    del fake_services._services["project"]
    svc = fake_services.get("project")
    assert type(svc) is ProjectService
    return svc


def test_resolve_file_path_success(
    real_project_service: ProjectService,
    project_path: pathlib.Path,
    app_metadata: AppMetadata,
):
    project_file = project_path / f"{app_metadata.name}.yaml"
    project_file.touch()

    assert real_project_service.resolve_project_file_path() == project_file


def test_resolve_file_path_missing(
    real_project_service: ProjectService, project_path: pathlib.Path
):
    with pytest.raises(
        errors.ProjectFileMissingError,
        match=rf"Project file '[a-z]+.yaml' not found in '{project_path}'.",
    ):
        real_project_service.resolve_project_file_path()


@pytest.mark.parametrize(
    ("project_yaml", "expected"),
    [
        pytest.param("{}", {}, id="empty-dict"),
        pytest.param("name: thing!", {"name": "thing!"}, id="name-only"),
    ],
)
def test_load_raw_project(
    real_project_service: ProjectService, project_path, project_yaml, expected
):
    (project_path / "testcraft.yaml").write_text(project_yaml)

    assert real_project_service._load_raw_project() == expected


@pytest.mark.parametrize(
    ("invalid_yaml", "details"),
    [
        ("", "Project file should be a YAML mapping, not 'NoneType'"),
        ("'Hello'", "Project file should be a YAML mapping, not 'str'"),
    ],
)
def test_load_raw_project_invalid(
    real_project_service: ProjectService, project_path, invalid_yaml, details
):
    (project_path / "testcraft.yaml").write_text(invalid_yaml)

    with pytest.raises(
        errors.ProjectFileInvalidError, match="^Invalid project file.$"
    ) as exc_info:
        real_project_service._load_raw_project()

    assert exc_info.value.details == details


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
        *(
            pytest.param(
                {"unvectored": {"build-on": str(arch), "build-for": "all"}},
                {"unvectored": {"build-on": [str(arch)], "build-for": ["all"]}},
                id=f"vectorise-{arch}",
            )
            for arch in craft_platforms.DebianArchitecture
        ),
        pytest.param(
            {"my-platform": {"build-on": ["ppc64el"]}},
            {"my-platform": {"build-on": ["ppc64el"]}},
            id="only-build-on-bad-name",
        ),
        pytest.param(
            {"ppc64el": {"build-on": ["amd64", "riscv64"]}},
            {"ppc64el": {"build-on": ["amd64", "riscv64"], "build-for": ["ppc64el"]}},
            id="only-build-on-valid-name",
        ),
        pytest.param(
            {"all": {"build-on": "riscv64"}},
            {"all": {"build-on": ["riscv64"], "build-for": ["all"]}},
            id="lazy-all",
        ),
        pytest.param(
            {"s390x": {"build-on": "ppc64el", "build-for": None}},
            {"s390x": {"build-on": ["ppc64el"], "build-for": ["s390x"]}},
            id="null-build-for-valid-name",
        ),
    ],
)
def test_get_platforms(
    real_project_service: ProjectService,
    platforms: dict[str, dict[str, list[str] | None]],
    expected,
):
    real_project_service._load_raw_project = lambda: {"platforms": platforms}  # type: ignore  # noqa: PGH003

    assert real_project_service.get_platforms() == expected


@pytest.mark.parametrize(
    ("platforms", "match"),
    [
        (None, "should be a valid dictionary"),
        ({"invalid": None}, r"platforms\.invalid\n.+should be a valid dictionary"),
        (
            {"my-pf": {"build-on": ["amd66"]}},
            "'amd66' is not a valid Debian architecture",
        ),
    ],
)
def test_get_platforms_bad_value(
    real_project_service: ProjectService, platforms, match
):
    real_project_service._load_raw_project = lambda: {"platforms": platforms}  # type: ignore  # noqa: PGH003

    with pytest.raises(pydantic.ValidationError, match=match):
        real_project_service.get_platforms()


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param({}, {"version": ""}, id="empty"),
        pytest.param(
            {"version": "3.14", "unrelated": "pi"},
            {"version": "3.14"},
            id="version-set",
        ),
    ],
)
def test_get_project_vars(real_project_service: ProjectService, data, expected):
    assert real_project_service._get_project_vars(data) == expected


@given(
    build_on=strategies.sampled_from(craft_platforms.DebianArchitecture),
    build_for=strategies.text(),
    platform=strategies.text(),
)
def test_get_partitions_for(build_on, build_for, platform):
    svc = ProjectService(None, None, project_dir=None)  # type: ignore[arg-type]
    assert (
        svc.get_partitions_for(
            platform=platform,
            build_for=build_for,
            build_on=build_on,
        )
        is None
    )


@pytest.mark.parametrize("build_for", [*craft_platforms.DebianArchitecture, "all"])
@pytest.mark.usefixtures("fake_host_architecture")
def test_partitions(
    fake_project_file,
    real_project_service: ProjectService,
    fake_platform: str,
    build_for: str,
):
    real_project_service.configure(build_for=build_for, platform=fake_platform)
    assert real_project_service.partitions is None


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
    real_project_service: ProjectService,
    project_data,
    build_for,
    fake_host_architecture,
    fake_platform,
    expected,
):
    real_project_service._expand_environment(
        project_data,
        platform=fake_platform,
        build_for=build_for,
        build_on=fake_host_architecture,
    )
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
    real_project_service: ProjectService,
    project_data,
    expected,
    fake_host_architecture,
    fake_platform,
):
    real_project_service._expand_environment(
        project_data,
        platform=fake_platform,
        build_for="riscv64",
        build_on=fake_host_architecture,
    )
    assert project_data == expected


@pytest.mark.parametrize(
    "project_data",
    [
        pytest.param(
            {
                "name": "my-name",
                "version": "1.2.3",
                "parts": {
                    "my-part": {
                        "plugin": "nil",
                        "override-build": "echo $CRAFT_STAGE",
                    }
                },
            },
        ),
    ],
)
@pytest.mark.usefixtures("managed_mode")
def test_expand_environment_managed_mode(
    real_project_service: ProjectService,
    project_data,
    fake_host_architecture,
    fake_platform,
):
    real_project_service._expand_environment(
        project_data,
        platform=fake_platform,
        build_for="riscv64",
        build_on=fake_host_architecture,
    )
    assert project_data["parts"]["my-part"]["override-build"] == "echo /root/stage"


@pytest.mark.parametrize(
    "build_for", [arch.value for arch in craft_platforms.DebianArchitecture]
)
@pytest.mark.usefixtures("enable_partitions")
def test_expand_environment_stage_dirs(
    project_service: ProjectService,
    build_for: str,
    project_path: pathlib.Path,
    fake_host_architecture,
    fake_platform: str,
):
    # The fake project service generates platforms based on its build-for and platform.
    # This is to ensure that we have dynamic partition sets that can vary based on
    # the platform.
    default_stage_dir = project_path / "stage"
    platform_stage_dir = project_path / f"partitions/{fake_platform}/stage"
    build_for_stage_dir = project_path / f"partitions/{build_for}/stage"
    default_prime_dir = project_path / "prime"
    platform_prime_dir = project_path / f"partitions/{fake_platform}/prime"
    build_for_prime_dir = project_path / f"partitions/{build_for}/prime"
    platform_env = fake_platform.upper().replace("-", "_")
    build_for_env = build_for.upper().replace("-", "_")
    my_part = {
        "plugin": "nil",
        "override-stage": f"echo $CRAFT_STAGE\necho $CRAFT_DEFAULT_STAGE\necho $CRAFT_{platform_env}_STAGE\necho $CRAFT_{build_for_env}_STAGE",
        "override-prime": f"echo $CRAFT_PRIME\necho $CRAFT_DEFAULT_PRIME\necho $CRAFT_{platform_env}_PRIME\necho $CRAFT_{build_for_env}_PRIME",
    }
    data = {"parts": {"my-part": my_part}}
    project_service._expand_environment(
        data,
        platform=fake_platform,
        build_for=build_for,
        build_on=fake_host_architecture,
    )
    assert data["parts"]["my-part"]["override-stage"] == textwrap.dedent(
        f"""\
        echo {default_stage_dir}
        echo {default_stage_dir}
        echo {platform_stage_dir}
        echo {build_for_stage_dir}"""
    )
    assert data["parts"]["my-part"]["override-prime"] == textwrap.dedent(
        f"""\
        echo {default_prime_dir}
        echo {default_prime_dir}
        echo {platform_prime_dir}
        echo {build_for_prime_dir}"""
    )


@pytest.mark.parametrize(
    "build_for", [arch.value for arch in craft_platforms.DebianArchitecture]
)
@pytest.mark.parametrize(
    "build_on", [arch.value for arch in craft_platforms.DebianArchitecture]
)
@pytest.mark.usefixtures("fake_project_file")
def test_preprocess(
    mocker: pytest_mock.MockFixture,
    real_project_service: ProjectService,
    build_for,
    build_on,
    fake_platform,
):
    mock_app_preprocess = mocker.patch.object(
        real_project_service, "_app_preprocess_project"
    )

    project = real_project_service._preprocess(
        build_for=build_for, build_on=build_on, platform=fake_platform
    )

    mock_app_preprocess.assert_called_once_with(
        real_project_service.get_raw(),
        build_on=build_on,
        build_for=build_for,
        platform=fake_platform,
    )

    assert project == real_project_service.get_raw()


@pytest.mark.parametrize(
    "build_for", [arch.value for arch in craft_platforms.DebianArchitecture]
)
@pytest.mark.parametrize(
    "build_on", [arch.value for arch in craft_platforms.DebianArchitecture]
)
@pytest.mark.usefixtures("fake_project_file")
def test_render_for(
    real_project_service: ProjectService, build_for, build_on, fake_platform
):
    result = real_project_service.render_for(
        build_for=build_for, build_on=build_on, platform=fake_platform
    )

    assert result.parts["some-part"]["build-environment"][1]["BUILD_FOR"] == build_for

    # The actual host value can be removed when here when we fix
    # https://github.com/canonical/craft-parts/issues/1018
    expected_build_ons = (
        build_on,
        craft_platforms.DebianArchitecture.from_host().value,
    )
    actual_build_on = result.parts["some-part"]["build-environment"][0]["BUILD_ON"]
    assert actual_build_on in expected_build_ons


@pytest.mark.usefixtures("platform_independent_project", "fake_project_file")
def test_render_for_platform_independent(
    real_project_service: ProjectService,
    fake_host_architecture,
):
    result = real_project_service.render_for(
        build_for="all",
        build_on=fake_host_architecture,
        platform="platform-independent",
    )

    assert (
        result.parts["some-part"]["build-environment"][1]["BUILD_FOR"]
        != fake_host_architecture
    )

    # The actual host value can be removed when here when we fix
    # https://github.com/canonical/craft-parts/issues/1018
    expected_build_ons = (
        fake_host_architecture,
        craft_platforms.DebianArchitecture.from_host().value,
    )
    actual_build_on = result.parts["some-part"]["build-environment"][0]["BUILD_ON"]
    assert actual_build_on in expected_build_ons


@pytest.mark.parametrize(
    "build_for", [arch.value for arch in craft_platforms.DebianArchitecture]
)
@pytest.mark.parametrize(
    "build_on", [arch.value for arch in craft_platforms.DebianArchitecture]
)
@pytest.mark.parametrize("platform", ["invalid"])
@pytest.mark.usefixtures("fake_project_file")
def test_render_for_invalid_platform(
    real_project_service: ProjectService, build_for, build_on, platform
):
    with pytest.raises(errors.InvalidPlatformError) as exc_info:
        real_project_service.render_for(
            build_for=build_for, build_on=build_on, platform=platform
        )

    assert cast(str, exc_info.value.details).startswith("Valid platforms are: '")


@pytest.mark.parametrize(
    "build_for", [*(arch.value for arch in craft_platforms.DebianArchitecture), "all"]
)
@pytest.mark.usefixtures("fake_project_file")
def test_cannot_reconfigure(
    real_project_service: ProjectService, build_for, fake_platform
):
    real_project_service.configure(platform=fake_platform, build_for=build_for)

    # Test that we can't re-render no matter the arguments.
    with pytest.raises(RuntimeError, match="Project is already configured."):
        real_project_service.configure(platform=fake_platform, build_for=build_for)

    with pytest.raises(RuntimeError, match="Project is already configured."):
        real_project_service.configure(platform=fake_platform, build_for=None)

    with pytest.raises(RuntimeError, match="Project is already configured."):
        real_project_service.configure(build_for=build_for, platform=None)

    with pytest.raises(RuntimeError, match="Project is already configured."):
        real_project_service.configure(platform=None, build_for=None)


@pytest.mark.usefixtures("fake_project_file")
def test_configure_bad_build_for(
    real_project_service: ProjectService,
    fake_project_file: pathlib.Path,
):
    """Test that we get a good error message given a bad build-for platform."""
    with pytest.raises(
        errors.CraftValidationError, match="not a valid Debian architecture"
    ):
        real_project_service.configure(platform=None, build_for="invalid")


@pytest.mark.parametrize(
    "build_for", [arch.value for arch in craft_platforms.DebianArchitecture]
)
@pytest.mark.usefixtures("fake_project_file")
def test_get_by_build_for_and_platform(
    real_project_service: ProjectService, build_for, fake_platform
):
    real_project_service.configure(platform=fake_platform, build_for=build_for)
    result = real_project_service.get()
    assert (
        result.parts["some-part"]["build-environment"][0]["BUILD_ON"]
        == craft_platforms.DebianArchitecture.from_host().value
    )
    assert result.parts["some-part"]["build-environment"][1]["BUILD_FOR"] == build_for


@pytest.mark.usefixtures("fake_project_file")
def test_get_by_platform(real_project_service: ProjectService, fake_platform: str):
    real_project_service.configure(platform=fake_platform, build_for=None)
    result = real_project_service.get()
    assert (
        result.parts["some-part"]["build-environment"][0]["BUILD_ON"]
        == craft_platforms.DebianArchitecture.from_host().value
    )
    build_for = cast(dict, result.platforms)[fake_platform].build_for[0]
    assert result.parts["some-part"]["build-environment"][1]["BUILD_FOR"] == build_for


@pytest.mark.usefixtures("fake_project_file")
@pytest.mark.parametrize(
    "build_for", [arch.value for arch in craft_platforms.DebianArchitecture]
)
def test_get_by_build_for(
    real_project_service: ProjectService, build_for: str, fake_host_architecture
):
    try:
        real_project_service.configure(build_for=build_for, platform=None)
    except RuntimeError as exc:
        pytest.skip(f"Not a valid build on/for combo: {exc}")
    # This test takes two paths because not all build-on/build-for combinations are
    # valid. If the combination is valid, we check that we got the expected output.
    # If the combination is invalid, we check that the error was correct.
    try:
        result = real_project_service.get()
    except RuntimeError as exc:
        assert (  # noqa: PT017
            exc.args[0]
            == f"Cannot generate a project that builds on {fake_host_architecture} and builds for {build_for}"
        )
    else:
        assert (
            result.parts["some-part"]["build-environment"][0]["BUILD_ON"]
            == craft_platforms.DebianArchitecture.from_host().value
        )
        assert (
            result.parts["some-part"]["build-environment"][1]["BUILD_FOR"] == build_for
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"build_for": "all"}, id="build-for-all"),
        pytest.param({"platform": "platform-independent"}, id="select-platform"),
        pytest.param({}, id="empty"),
    ],
)
@pytest.mark.usefixtures("platform_independent_project", "fake_project_file")
def test_get_platform_independent(
    real_project_service: ProjectService, fake_host_architecture, kwargs
):
    configure_args = {"build_for": None, "platform": None}
    configure_args.update(kwargs)
    real_project_service.configure(**configure_args)
    result = real_project_service.get()

    assert (
        result.parts["some-part"]["build-environment"][0]["BUILD_ON"]
        == fake_host_architecture
    )
    assert result.parts["some-part"]["build-environment"][1]["BUILD_FOR"] not in (
        fake_host_architecture,
        "all",
    )


def test_get_not_configured(real_project_service: ProjectService):
    with pytest.raises(RuntimeError, match="Project not configured yet."):
        real_project_service.get()


@pytest.mark.usefixtures("fake_project_file")
def test_get_already_rendered(real_project_service: ProjectService):
    real_project_service.configure(platform=None, build_for=None)
    rendered = real_project_service.get()

    assert real_project_service.get() is rendered


def test_mandatory_adoptable_fields(
    app_metadata, real_project_service: ProjectService, fake_project_file: pathlib.Path
):
    """Verify if mandatory adoptable fields are defined if not using adopt-info."""
    real_project_service._app = dataclasses.replace(
        app_metadata, mandatory_adoptable_fields=["version", "license"]
    )

    project_yaml = fake_project_file.read_text()
    fake_project_file.write_text(project_yaml.replace("license:", "# licence:"))

    real_project_service.configure(platform=None, build_for=None)
    with pytest.raises(errors.CraftValidationError) as exc_info:
        _ = real_project_service.get()

    assert (
        str(exc_info.value)
        == "'adopt-info' not set and required fields are missing: 'license'"
    )
