# This file is part of craft-application.
#
# Copyright 2024 Canonical Ltd.
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
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Unit tests for the build plan service."""

import collections
from collections.abc import Collection
from typing import Literal
from unittest import mock

import craft_platforms
import pytest
import pytest_check
import pytest_mock
from craft_application.errors import EmptyBuildPlanError
from craft_application.services.buildplan import BuildPlanService
from craft_application.services.service_factory import ServiceFactory
from craft_cli.pytest_plugin import RecordingEmitter
from craft_platforms import BuildInfo, DebianArchitecture, DistroBase


def test__gen_exhaustive_build_plan(
    mocker: pytest_mock.MockFixture, build_plan_service: BuildPlanService, app_metadata
):
    stub_project = {}
    mock_create_build_plan = mocker.patch("craft_platforms.get_build_plan")

    build_plan_service._gen_exhaustive_build_plan(stub_project)

    mock_create_build_plan.assert_called_once_with(
        app=app_metadata.name, project_data=stub_project
    )


def test_plan_empty(
    mocker: pytest_mock.MockFixture,
    build_plan_service: BuildPlanService,
):
    mocker.patch.object(build_plan_service, "create_build_plan", return_value=[])
    with pytest.raises(EmptyBuildPlanError):
        build_plan_service.plan()


_base = DistroBase("", "")
_pc_on_amd64_for_amd64 = BuildInfo(
    platform="pc",
    build_on=DebianArchitecture.AMD64,
    build_for=DebianArchitecture.AMD64,
    build_base=_base,
)
_pc_on_amd64_for_i386 = BuildInfo(
    platform="legacy-pc",
    build_on=DebianArchitecture.AMD64,
    build_for=DebianArchitecture.I386,
    build_base=_base,
)
_amd64_on_amd64_for_amd64 = BuildInfo(
    platform="amd64",
    build_on=DebianArchitecture.AMD64,
    build_for=DebianArchitecture.AMD64,
    build_base=_base,
)
_i386_on_amd64_for_i386 = BuildInfo(
    platform="i386",
    build_on=DebianArchitecture.AMD64,
    build_for=DebianArchitecture.I386,
    build_base=_base,
)
_i386_on_i386_for_i386 = BuildInfo(
    platform="i386",
    build_on=DebianArchitecture.I386,
    build_for=DebianArchitecture.I386,
    build_base=_base,
)


@pytest.mark.parametrize(
    ("plan", "platform", "build_for", "build_on", "result"),
    [
        pytest.param(
            [_pc_on_amd64_for_amd64],
            None,
            None,
            DebianArchitecture.AMD64,
            [_pc_on_amd64_for_amd64],
            id="0",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64],
            "pc",
            None,
            DebianArchitecture.AMD64,
            [_pc_on_amd64_for_amd64],
            id="1",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64],
            "legacy-pc",
            None,
            DebianArchitecture.AMD64,
            [],
            id="2",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64],
            None,
            DebianArchitecture.AMD64,
            DebianArchitecture.AMD64,
            [_pc_on_amd64_for_amd64],
            id="3",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64],
            "pc",
            DebianArchitecture.AMD64,
            DebianArchitecture.AMD64,
            [_pc_on_amd64_for_amd64],
            id="4",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64],
            "legacy-pc",
            DebianArchitecture.AMD64,
            DebianArchitecture.AMD64,
            [],
            id="5",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64],
            None,
            DebianArchitecture.I386,
            DebianArchitecture.AMD64,
            [],
            id="6",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64],
            None,
            DebianArchitecture.AMD64,
            DebianArchitecture.I386,
            [],
            id="7",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            None,
            DebianArchitecture.I386,
            DebianArchitecture.AMD64,
            [_pc_on_amd64_for_i386],
            id="8",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            "pc",
            DebianArchitecture.AMD64,
            DebianArchitecture.I386,
            [],
            id="9",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            "legacy-pc",
            DebianArchitecture.I386,
            DebianArchitecture.AMD64,
            [_pc_on_amd64_for_i386],
            id="10",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            None,
            DebianArchitecture.I386,
            DebianArchitecture.I386,
            [],
            id="11",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            None,
            None,
            DebianArchitecture.I386,
            [],
            id="12",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            "legacy-pc",
            None,
            DebianArchitecture.I386,
            [],
            id="13",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            None,
            None,
            DebianArchitecture.AMD64,
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            id="14",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _pc_on_amd64_for_i386],
            "legacy-pc",
            None,
            DebianArchitecture.AMD64,
            [_pc_on_amd64_for_i386],
            id="15",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _amd64_on_amd64_for_amd64],
            None,
            DebianArchitecture.AMD64,
            DebianArchitecture.AMD64,
            [_pc_on_amd64_for_amd64, _amd64_on_amd64_for_amd64],
            id="16",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _amd64_on_amd64_for_amd64],
            DebianArchitecture.AMD64,
            None,
            DebianArchitecture.AMD64,
            [_amd64_on_amd64_for_amd64],
            id="17",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _amd64_on_amd64_for_amd64],
            DebianArchitecture.AMD64,
            DebianArchitecture.AMD64,
            DebianArchitecture.AMD64,
            [_amd64_on_amd64_for_amd64],
            id="18",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386],
            None,
            DebianArchitecture.I386,
            DebianArchitecture.AMD64,
            [_i386_on_amd64_for_i386],
            id="19",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386],
            DebianArchitecture.AMD64,
            None,
            DebianArchitecture.AMD64,
            [],
            id="20",
        ),
        pytest.param(
            [
                _pc_on_amd64_for_amd64,
                _amd64_on_amd64_for_amd64,
                _i386_on_amd64_for_i386,
            ],
            None,
            DebianArchitecture.AMD64,
            DebianArchitecture.AMD64,
            [_pc_on_amd64_for_amd64, _amd64_on_amd64_for_amd64],
            id="21",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386],
            DebianArchitecture.I386,
            DebianArchitecture.I386,
            DebianArchitecture.AMD64,
            [_i386_on_amd64_for_i386],
            id="22",
        ),
        pytest.param(
            [
                _pc_on_amd64_for_amd64,
                _amd64_on_amd64_for_amd64,
                _i386_on_amd64_for_i386,
            ],
            None,
            DebianArchitecture.I386,
            DebianArchitecture.AMD64,
            [_i386_on_amd64_for_i386],
            id="23",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _amd64_on_amd64_for_amd64],
            None,
            DebianArchitecture.I386,
            DebianArchitecture.AMD64,
            [],
            id="24",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386, _i386_on_i386_for_i386],
            DebianArchitecture.AMD64,
            None,
            DebianArchitecture.AMD64,
            [],
            id="25",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386, _i386_on_i386_for_i386],
            DebianArchitecture.AMD64,
            None,
            DebianArchitecture.I386,
            [],
            id="26",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386, _i386_on_i386_for_i386],
            DebianArchitecture.I386,
            None,
            DebianArchitecture.AMD64,
            [_i386_on_amd64_for_i386],
            id="27",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386, _i386_on_i386_for_i386],
            DebianArchitecture.I386,
            None,
            DebianArchitecture.I386,
            [_i386_on_i386_for_i386],
            id="28",
        ),
        pytest.param(
            [_pc_on_amd64_for_amd64, _i386_on_amd64_for_i386, _i386_on_i386_for_i386],
            None,
            DebianArchitecture.I386,
            DebianArchitecture.I386,
            [_i386_on_i386_for_i386],
            id="29",
        ),
        # Filters without a build-on. Which specific items are selected here is an
        # implementation detail and may change.
        pytest.param(
            [
                _pc_on_amd64_for_amd64,
                _pc_on_amd64_for_i386,
                _amd64_on_amd64_for_amd64,
                _i386_on_amd64_for_i386,
                _i386_on_i386_for_i386,
            ],
            None,
            None,
            None,
            [
                _pc_on_amd64_for_amd64,
                _pc_on_amd64_for_i386,
                _amd64_on_amd64_for_amd64,
                _i386_on_amd64_for_i386,
            ],
            id="empty-filter",
        ),
        pytest.param(
            [
                _pc_on_amd64_for_amd64,
                _pc_on_amd64_for_i386,
                _amd64_on_amd64_for_amd64,
                _i386_on_amd64_for_i386,
            ],
            None,
            "i386",
            None,
            [
                _pc_on_amd64_for_i386,
                _i386_on_amd64_for_i386,
            ],
            id="build-on-anything-for-i386",
        ),
    ],
)
def test_filter_plan(
    build_plan_service: BuildPlanService,
    plan: list[BuildInfo],
    platform: str | None,
    build_for: craft_platforms.DebianArchitecture | Literal["all"] | None,
    build_on: craft_platforms.DebianArchitecture | None,
    result,
):
    assert (
        list(
            build_plan_service._filter_plan(
                plan,
                platforms=[platform] if platform else None,
                build_for=[build_for] if build_for else None,
                build_on=[build_on] if build_on else None,
            )
        )
        == result
    )


def check_plan(
    plan: Collection[BuildInfo],
    *,
    min_length: int = 1,
    max_length: int = 0,
    build_on: str | None = None,
    build_for: str | None = None,
    platform: str | None = None,
):
    assert len(plan) >= min_length
    if max_length:
        assert len(plan) <= max_length
    platform_items = collections.defaultdict(list)
    for item in plan:
        platform_items[item.platform].append(item)
        if build_on:
            pytest_check.equal(item.build_on, build_on)
        if build_for:
            pytest_check.equal(item.build_for, build_for)
        if platform:
            pytest_check.equal(item.platform, platform)

    # Each platform must contain either 0 or 1 builds.
    for name, items in platform_items.items():
        assert len(items) == 1, f"Too many builds for platform {name!r}: {items}"


def test_create_build_plan_no_filter(
    build_plan_service: BuildPlanService,
    fake_services: ServiceFactory,
    emitter: RecordingEmitter,
    fake_host_architecture,
):
    plan = build_plan_service.create_build_plan(
        platforms=None,
        build_for=None,
        build_on=None,
    )

    check_plan(plan)


@pytest.mark.usefixtures("platform_independent_project")
def test_create_build_plan_no_filter_platform_independent(
    build_plan_service: BuildPlanService,
    fake_services: ServiceFactory,
    emitter: RecordingEmitter,
    fake_host_architecture,
):
    plan = build_plan_service.create_build_plan(
        platforms=None,
        build_for=None,
        build_on=None,
    )

    check_plan(plan)


def test_create_build_plan_platform_filter(
    build_plan_service: BuildPlanService,
    fake_services: ServiceFactory,
    emitter: RecordingEmitter,
    fake_host_architecture,
    fake_platform,
):
    plan = build_plan_service.create_build_plan(
        platforms=[fake_platform],
        build_for=None,
        build_on=None,
    )

    check_plan(
        plan,
        min_length=0,  # Not all platforms in our project can be built on all archs
        platform=fake_platform,
    )


@pytest.mark.usefixtures("platform_independent_project")
def test_create_build_plan_platform_filter_all(
    build_plan_service: BuildPlanService,
    fake_services: ServiceFactory,
    emitter: RecordingEmitter,
    fake_host_architecture,
):
    plan = build_plan_service.create_build_plan(
        platforms=["platform-independent"],
        build_for=None,
        build_on=None,
    )

    check_plan(
        plan,
        max_length=1,
        platform="platform-independent",
    )


@pytest.mark.parametrize("build_for", craft_platforms.DebianArchitecture)
def test_create_build_plan_build_for_filter(
    build_plan_service: BuildPlanService,
    fake_services: ServiceFactory,
    emitter: RecordingEmitter,
    fake_host_architecture,
    build_for,
):
    plan = build_plan_service.create_build_plan(
        platforms=None,
        build_for=[str(build_for)],
        build_on=None,
    )

    check_plan(
        plan,
        min_length=0,  # Not all build-on/build-for combos exist.
        build_for=build_for,
    )


@pytest.mark.usefixtures("platform_independent_project")
def test_create_build_plan_build_for_filter_platform_independent(
    build_plan_service: BuildPlanService,
    fake_services: ServiceFactory,
    emitter: RecordingEmitter,
    fake_host_architecture,
):
    plan = build_plan_service.create_build_plan(
        platforms=None,
        build_for=["all"],
        build_on=None,
    )

    check_plan(
        plan,
        min_length=1,
        max_length=1,
        build_for="all",
    )


@pytest.mark.parametrize("build_on", craft_platforms.DebianArchitecture)
def test_create_build_plan_build_on_filter(
    build_plan_service: BuildPlanService,
    fake_services: ServiceFactory,
    emitter: RecordingEmitter,
    fake_host_architecture,
    build_on,
):
    plan = build_plan_service.create_build_plan(
        platforms=None,
        build_for=None,
        build_on=[build_on],
    )

    assert (
        mock.call(
            "trace",
            f"No build-on filter set, using the default of {[fake_host_architecture.value]}",
        )
        not in emitter.interactions
    )

    check_plan(
        plan,
        min_length=0,  # Not all build-on/build-for combos exist.
        build_on=build_on,
    )


@pytest.mark.usefixtures("platform_independent_project")
@pytest.mark.parametrize("build_on", craft_platforms.DebianArchitecture)
def test_create_build_plan_build_on_filter_platform_independent(
    build_plan_service: BuildPlanService,
    fake_services: ServiceFactory,
    emitter: RecordingEmitter,
    fake_host_architecture,
    build_on,
):
    plan = build_plan_service.create_build_plan(
        platforms=None,
        build_for=None,
        build_on=[build_on],
    )

    assert (
        mock.call(
            "trace",
            f"No build-on filter set, using the default of {[fake_host_architecture.value]}",
        )
        not in emitter.interactions
    )

    check_plan(
        plan,
        max_length=1,
        build_on=build_on,
    )


@pytest.mark.parametrize("build_for", craft_platforms.DebianArchitecture)
def test_create_build_plan_multiple_filters(
    build_plan_service: BuildPlanService,
    fake_services: ServiceFactory,
    fake_platform,
    fake_host_architecture,
    build_for,
):
    plan = build_plan_service.create_build_plan(
        platforms=[fake_platform],
        build_for=[build_for],
        build_on=[fake_host_architecture],
    )

    check_plan(
        plan,
        min_length=0,
        max_length=1,
        platform=fake_platform,
        build_for=build_for,
        build_on=fake_host_architecture,
    )


def test_create_build_plan_no_platforms(
    build_plan_service: BuildPlanService,
    fake_services: ServiceFactory,
    mocker: pytest_mock.MockFixture,
):
    project_service = fake_services.get("project")
    mock_get_raw = mocker.patch.object(
        project_service, "get_raw", return_value={"base": "ubuntu@devel"}
    )
    mock_get_platforms = mocker.patch.object(
        project_service, "get_platforms", return_value={}
    )

    plan = build_plan_service.create_build_plan(
        platforms=None, build_for=None, build_on=None
    )

    assert plan == []
    mock_get_raw.assert_called_once_with()
    mock_get_platforms.assert_called_once_with()


def test_create_build_plan_filters_to_empty(build_plan_service: BuildPlanService):
    assert (
        build_plan_service.create_build_plan(
            platforms=["not-a-platform"],
            build_for=None,
            build_on=None,
        )
        == []
    )


def test_set_platforms_resets_cached_plan(mocker, build_plan_service: BuildPlanService):
    build_plan_service.plan()
    mock_creator = mocker.patch.object(build_plan_service, "create_build_plan")
    build_plan_service.set_platforms("zero", "mind the gap")
    mock_creator.assert_not_called()
    build_plan_service.plan()
    build_plan_service.plan()  # This time it should keep the cache.
    mock_creator.assert_called_once_with(
        platforms=["zero", "mind the gap"],
        build_for=None,
        build_on=[craft_platforms.DebianArchitecture.from_host()],
    )


def test_set_build_fors_resets_cached_plan(
    mocker, build_plan_service: BuildPlanService
):
    build_plan_service.plan()
    mock_creator = mocker.patch.object(build_plan_service, "create_build_plan")
    build_plan_service.set_build_fors("riscv64")
    mock_creator.assert_not_called()
    build_plan_service.plan()
    build_plan_service.plan()  # This time it should keep the cache.
    mock_creator.assert_called_once_with(
        platforms=None,
        build_for=["riscv64"],
        build_on=[craft_platforms.DebianArchitecture.from_host()],
    )
