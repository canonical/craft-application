# This file is part of craft_application.
#
# Copyright 2023-2024 Canonical Ltd.
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
"""Unit tests for parts lifecycle."""

from __future__ import annotations

import dataclasses
import re
from pathlib import Path
from typing import TYPE_CHECKING
from unittest import mock

import craft_parts
import craft_parts.callbacks
import craft_platforms
import distro
import pytest
import pytest_check
from craft_application import errors, models, util
from craft_application.errors import EmptyBuildPlanError, PartsLifecycleError
from craft_application.services import lifecycle
from craft_application.util import repositories
from craft_parts import (
    Action,
    ActionType,
    LifecycleManager,
    Part,
    PartInfo,
    ProjectInfo,
    Step,
    StepInfo,
)
from craft_parts.executor import (
    ExecutionContext,  # pyright: ignore[reportPrivateImportUsage]
)

if TYPE_CHECKING:
    from craft_application.services.buildplan import BuildPlanService


def skip_if_build_plan_empty(build_planner: BuildPlanService):
    try:
        build_planner.plan()
    except EmptyBuildPlanError:
        pytest.skip(reason="Empty build plan")


# region Local fixtures
class FakePartsLifecycle(lifecycle.LifecycleService):
    def _init_lifecycle_manager(self) -> LifecycleManager:
        mock_lcm = mock.Mock(spec=LifecycleManager)
        mock_aex = mock.MagicMock(spec=ExecutionContext)
        mock_info = mock.MagicMock(spec=ProjectInfo)
        mock_info.get_project_var = lambda _: "foo"
        mock_lcm.action_executor.return_value = mock_aex
        mock_lcm.project_info = mock_info
        return mock_lcm


@pytest.fixture
def fake_parts_lifecycle(app_metadata, fake_project, fake_services, tmp_path):
    work_dir = tmp_path / "work"
    cache_dir = tmp_path / "cache"
    fake_service = FakePartsLifecycle(
        app_metadata,
        fake_services,
        work_dir=work_dir,
        cache_dir=cache_dir,
    )
    fake_service.setup()
    return fake_service


# endregion
# region Helper function tests
@pytest.mark.parametrize(
    ("step", "message"),
    [
        (Step.PULL, "Pulling my-part"),
        (Step.BUILD, "Building my-part"),
        (Step.OVERLAY, "Overlaying my-part"),
        (Step.STAGE, "Staging my-part"),
        (Step.PRIME, "Priming my-part"),
    ],
)
def test_get_parts_action_message_run(step: Step, message: str):
    action = Action(
        "my-part",
        step,
        action_type=ActionType.RUN,
    )

    actual = lifecycle._get_parts_action_message(action)

    assert actual == message, f"Unexpected {actual!r}"


@pytest.mark.parametrize(
    ("step", "message"),
    [
        (Step.PULL, "Repulling my-part"),
        (Step.BUILD, "Rebuilding my-part"),
        (Step.OVERLAY, "Re-overlaying my-part"),
        (Step.STAGE, "Restaging my-part"),
        (Step.PRIME, "Repriming my-part"),
    ],
)
def test_get_parts_re_action_message_run(step: Step, message: str):
    action = Action(
        "my-part",
        step,
        action_type=ActionType.RERUN,
    )

    actual = lifecycle._get_parts_action_message(action)

    assert actual == message, f"Unexpected {actual!r}"


@pytest.mark.parametrize(
    ("step", "message"),
    [
        (Step.PULL, "Skipping pull for my-part"),
        (Step.BUILD, "Skipping build for my-part"),
        (Step.OVERLAY, "Skipping overlay for my-part"),
        (Step.STAGE, "Skipping stage for my-part"),
        (Step.PRIME, "Skipping prime for my-part"),
    ],
)
def test_get_parts_skip_action_message_run(step: Step, message: str):
    action = Action(
        "my-part",
        step,
        action_type=ActionType.SKIP,
    )

    actual = lifecycle._get_parts_action_message(action)

    assert actual == message, f"Unexpected {actual!r}"


@pytest.mark.parametrize(
    ("step", "message"),
    [
        (Step.PULL, "Updating sources for my-part"),
        (Step.BUILD, "Updating build for my-part"),
        (Step.OVERLAY, "Updating overlay for my-part"),
    ],
)
def test_get_parts_update_action_message_run(step: Step, message: str):
    action = Action(
        "my-part",
        step,
        action_type=ActionType.UPDATE,
    )

    actual = lifecycle._get_parts_action_message(action)

    assert actual == message, f"Unexpected {actual!r}"


@pytest.mark.parametrize(
    ("step", "message"),
    [
        (Step.PULL, "Pulling my-part (dirty)"),
        (Step.BUILD, "Building my-part (dirty)"),
        (Step.OVERLAY, "Overlaying my-part (dirty)"),
        (Step.STAGE, "Staging my-part (dirty)"),
        (Step.PRIME, "Priming my-part (dirty)"),
    ],
)
def get_parts_action_message_with_reason(step: Step, message: str):
    action = Action("my-part", step, action_type=ActionType.RUN, reason="dirty")

    actual = lifecycle._get_parts_action_message(action)

    assert actual == message, f"Unexpected {actual!r}"


def test_progress_messages(
    fake_services, fake_platform, fake_host_architecture, fake_parts_lifecycle, emitter
):
    fake_services.get("build_plan").set_platforms(fake_platform)
    skip_if_build_plan_empty(fake_services.get("build_plan"))
    actions = [
        Action("my-part", Step.PULL),
        Action("my-part", Step.BUILD),
        Action("my-part", Step.OVERLAY),
        Action("my-part", Step.STAGE),
        Action("my-part", Step.PRIME),
    ]

    lcm = fake_parts_lifecycle._lcm
    lcm.plan.return_value = actions

    fake_parts_lifecycle.run("prime")

    emitter.assert_progress("Pulling my-part")
    emitter.assert_progress("Building my-part")
    emitter.assert_progress("Overlaying my-part")
    emitter.assert_progress("Staging my-part")
    emitter.assert_progress("Priming my-part")


@pytest.mark.usefixtures("enable_overlay")
@pytest.mark.parametrize(
    ("step_name", "step"),
    [
        ("pull", Step.PULL),
        ("overlay", Step.OVERLAY),
        ("build", Step.BUILD),
        ("stage", Step.STAGE),
        ("prime", Step.PRIME),
    ],
)
def test_get_step_success(step_name, step):
    actual = lifecycle._get_step(step_name)

    assert actual == step


@pytest.mark.parametrize("step_name", ["overlay", "fake step"])
def test_get_step_failure(step_name):
    with pytest.raises(RuntimeError, match=f"Invalid target step {step_name!r}"):
        lifecycle._get_step(step_name)


# endregion
# region PartsLifecycle tests
def test_init_success(app_metadata, fake_project, fake_services, tmp_path):
    service = lifecycle.LifecycleService(
        app_metadata,
        fake_services,
        work_dir=tmp_path,
        cache_dir=tmp_path,
    )
    assert service._lcm is None
    service.setup()
    assert service._lcm is not None


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (
            craft_parts.errors.InvalidApplicationName("craft-application"),
            PartsLifecycleError("Application name 'craft-application' is invalid."),
        ),
        (
            TypeError("parts definition must be a dictionary"),
            TypeError("parts definition must be a dictionary"),
        ),
    ],
)
def test_init_parts_error(
    monkeypatch,
    app_metadata,
    fake_project,
    fake_services,
    new_dir,
    error,
    expected,
):
    mock_lifecycle = mock.Mock(side_effect=error)
    monkeypatch.setattr(lifecycle, "LifecycleManager", mock_lifecycle)

    service = lifecycle.LifecycleService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=new_dir,
        cache_dir=new_dir,
        platform=None,
    )

    with pytest.raises(type(expected)) as exc_info:
        service.setup()

    assert exc_info.value.args == expected.args
    assert mock_lifecycle.mock_calls[0].kwargs["ignore_local_sources"] == [
        "*.snap",
        "*.charm",
        "*.starcraft",
    ]


def test_init_parts_ignore_spread(
    app_metadata, fake_project, fake_services, monkeypatch, new_dir
):
    mock_lifecycle = mock.Mock()
    monkeypatch.setattr(lifecycle, "LifecycleManager", mock_lifecycle)

    service = lifecycle.LifecycleService(
        app_metadata,
        fake_services,
        work_dir=new_dir,
        cache_dir=new_dir,
    )

    extension_path = Path("spread/.extension")
    extension_path.parent.mkdir()
    extension_path.touch()

    service.setup()

    assert mock_lifecycle.mock_calls[0].kwargs["ignore_local_sources"] == [
        "*.snap",
        "*.charm",
        "*.starcraft",
        "spread.yaml",
        "spread",
    ]


def test_init_with_feature_package_repositories(
    app_metadata, fake_project, fake_services, tmp_path
):
    package_repositories = [{"type": "apt", "ppa": "ppa/ppa"}]
    fake_project.package_repositories = package_repositories.copy()
    fake_services.get("project").set(fake_project)

    service = lifecycle.LifecycleService(
        app_metadata,
        fake_services,
        work_dir=tmp_path,
        cache_dir=tmp_path,
        platform=None,
    )
    assert service._lcm is None
    service.setup()
    assert service._lcm is not None
    assert service._lcm._project_info.package_repositories == package_repositories


@pytest.mark.usefixtures("enable_partitions")
def test_init_with_partitions(
    app_metadata, fake_project, fake_services, tmp_path, fake_platform
):
    service = lifecycle.LifecycleService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=tmp_path,
        cache_dir=tmp_path,
        platform=None,
    )
    assert service._lcm is None
    service.setup()
    assert service._lcm is not None
    assert service._lcm._project_info.partitions[0] == "default"
    assert fake_platform in service._lcm._project_info.partitions


def test_prime_dir(lifecycle_service, tmp_path):
    prime_dir = lifecycle_service.prime_dir

    pytest_check.is_instance(prime_dir, Path)
    pytest_check.equal(prime_dir, tmp_path / "work/prime")


def test_project_info(lifecycle_service):
    info = lifecycle_service.project_info

    assert info.application_name == "testcraft"


def test_get_pull_assets(lifecycle_service):
    assets = lifecycle_service.get_pull_assets(part_name="my-part")

    assert assets == {"foo": "bar"}


def test_get_primed_stage_packages(lifecycle_service):
    pkgs = lifecycle_service.get_primed_stage_packages(part_name="my-part")

    assert pkgs == ["pkg1", "pkg2"]


@pytest.mark.parametrize(
    ("build_plan", "expected"),
    [
        ([], None),
        (
            [
                craft_platforms.BuildInfo(
                    "my-platform",
                    build_on=craft_platforms.DebianArchitecture.from_host(),
                    build_for="all",
                    build_base=craft_platforms.DistroBase("ubuntu", "24.04"),
                )
            ],
            None,
        ),
        (
            [
                craft_platforms.BuildInfo(
                    "my-platform",
                    build_on=craft_platforms.DebianArchitecture.from_host(),
                    build_for=craft_platforms.DebianArchitecture.AMD64,
                    build_base=craft_platforms.DistroBase("ubuntu", "24.04"),
                )
            ],
            "amd64",
        ),
        (
            [
                craft_platforms.BuildInfo(
                    "my-platform",
                    build_on=craft_platforms.DebianArchitecture.from_host(),
                    build_for=craft_platforms.DebianArchitecture.ARM64,
                    build_base=craft_platforms.DistroBase("ubuntu", "24.04"),
                )
            ],
            "arm64",
        ),
        (
            [
                craft_platforms.BuildInfo(
                    "my-platform",
                    build_on=craft_platforms.DebianArchitecture.from_host(),
                    build_for=craft_platforms.DebianArchitecture.RISCV64,
                    build_base=craft_platforms.DistroBase("ubuntu", "24.04"),
                )
            ],
            "riscv64",
        ),
    ],
)
def test_get_build_for(
    mocker,
    fake_host_architecture,
    fake_parts_lifecycle: lifecycle.LifecycleService,
    fake_services,
    build_plan: list[craft_platforms.BuildInfo],
    expected: str | None,
):
    mocker.patch.object(
        fake_services.get("build_plan"), "plan", return_value=build_plan
    )
    if expected is None:
        expected = fake_host_architecture

    actual = fake_parts_lifecycle._get_build_for()

    assert actual == expected


@pytest.mark.parametrize(
    "actions",
    [
        [],
        [Action("my-part", Step.PULL), Action("my-part", Step.BUILD)],
    ],
)
def test_run_success(
    fake_parts_lifecycle,
    actions,
    check,
    fake_services,
    fake_platform,
    fake_host_architecture,
):
    fake_services.get("build_plan").set_platforms(fake_platform)
    skip_if_build_plan_empty(fake_services.get("build_plan"))
    lcm = fake_parts_lifecycle._lcm
    lcm.plan.return_value = actions
    executor = lcm.action_executor.return_value.__enter__.return_value
    executor_calls = [
        mock.call.execute(action, stdout=mock.ANY, stderr=mock.ANY)
        for action in actions
    ]

    fake_parts_lifecycle.run("build")

    with check:
        lcm.plan.assert_called_once_with(Step.BUILD, part_names=None)
    with check:
        assert executor.method_calls == executor_calls


def test_run_no_step(
    fake_parts_lifecycle, fake_services, fake_platform, fake_host_architecture
):
    fake_services.get("build_plan").set_platforms(fake_platform)
    skip_if_build_plan_empty(fake_services.get("build_plan"))
    lcm = fake_parts_lifecycle._lcm
    executor = lcm.action_executor.return_value.__enter__.return_value

    fake_parts_lifecycle.run(None)

    # No calls to execute actions
    assert executor.method_calls == []


@pytest.mark.parametrize(
    ("err", "exc_class", "message_regex"),
    [
        (RuntimeError("yolo"), RuntimeError, "^Parts processing internal error: yolo$"),
        (OSError(0, "Hi"), PartsLifecycleError, "^Hi$"),
        (Exception("u wot m8"), PartsLifecycleError, "^Unknown error: u wot m8$"),
        (craft_parts.PartsError("parts error"), PartsLifecycleError, "^parts error$"),
    ],
)
def test_run_failure(
    fake_parts_lifecycle,
    fake_services,
    fake_platform,
    fake_host_architecture,
    err,
    exc_class,
    message_regex,
):
    fake_services.get("build_plan").set_platforms(fake_platform)
    skip_if_build_plan_empty(fake_services.get("build_plan"))
    fake_parts_lifecycle._lcm.plan.side_effect = err

    with pytest.raises(exc_class, match=message_regex):
        fake_parts_lifecycle.run("pull")


@pytest.mark.parametrize(
    ("part_names", "message"),
    [
        (["my-part", "your-part"], "Cleaning parts: my-part, your-part"),
        ([], "Cleaning all parts"),
        (None, "Cleaning all parts"),
    ],
)
def test_clean(part_names, message, emitter, fake_parts_lifecycle, check):
    fake_parts_lifecycle.clean(part_names)

    with check:
        emitter.assert_progress(message)
    with check:
        fake_parts_lifecycle._lcm.clean.assert_called_once_with(part_names=part_names)


def test_repr(fake_parts_lifecycle, app_metadata, fake_project):
    start = f"FakePartsLifecycle({app_metadata!r}, "

    actual = repr(fake_parts_lifecycle)

    pytest_check.is_true(actual.startswith(start))
    pytest_check.is_true(
        re.fullmatch(
            r"FakePartsLifecycle\(.+, work_dir=(Posix|Windows)Path\('.+'\), "
            r"cache_dir=(Posix|Windows)Path\('.+'\), .+\)",
            actual,
        ),
        f"Does not match expected regex: {actual}",
    )


def test_post_prime_success(fake_parts_lifecycle):
    step_info = StepInfo(
        part_info=PartInfo(
            fake_parts_lifecycle.project_info, part=Part("test-part", {})
        ),
        step=Step.PRIME,
    )

    assert not fake_parts_lifecycle.post_prime(step_info)


@pytest.mark.parametrize("step", [Step.PULL, Step.OVERLAY, Step.BUILD, Step.STAGE])
def test_post_prime_wrong_step(fake_parts_lifecycle, step):
    step_info = StepInfo(
        part_info=PartInfo(
            fake_parts_lifecycle.project_info,
            part=Part("test-part", {}),
        ),
        step=step,
    )

    with pytest.raises(RuntimeError, match="^Post-prime hook called after step: "):
        fake_parts_lifecycle.post_prime(step_info)


def test_run_lifecycle_build_for_all(
    app_metadata,
    fake_project,
    fake_services,
    tmp_path,
):
    """'build-for: [all]' should be converted to the host arch."""
    build_plan = [
        craft_platforms.BuildInfo(
            platform="platform1",
            build_on=craft_platforms.DebianArchitecture.from_host(),
            build_for="all",
            build_base=craft_platforms.DistroBase.from_linux_distribution(
                distro.LinuxDistribution()
            ),
        )
    ]
    work_dir = tmp_path / "work"

    service = lifecycle.LifecycleService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=work_dir,
        cache_dir=tmp_path / "cache",
        platform=None,
        build_plan=build_plan,
    )
    service.setup()

    assert (
        service.project_info.target_arch
        == craft_platforms.DebianArchitecture.from_host()
    )
    assert service.project_info.arch_build_for == util.get_host_architecture()


# endregion
# region Feature package repositories tests


@pytest.mark.parametrize(
    "local_keys_path",
    [None, Path("my/keys")],
)
def test_lifecycle_package_repositories(
    app_metadata,
    fake_project,
    fake_services,
    fake_platform,
    tmp_path,
    mocker,
    local_keys_path,
):
    """Test that package repositories installation is called in the lifecycle."""
    fake_services.get("build_plan").set_platforms(fake_platform)
    skip_if_build_plan_empty(fake_services.get("build_plan"))
    fake_repositories = [{"type": "apt", "ppa": "ppa/ppa"}]
    fake_project.package_repositories = fake_repositories.copy()
    fake_services.get("project").set(fake_project)
    work_dir = tmp_path / "work"

    service = lifecycle.LifecycleService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=work_dir,
        cache_dir=tmp_path / "cache",
        platform=None,
    )
    service.setup()
    mocker.patch.object(service, "_get_local_keys_path", return_value=local_keys_path)

    service._lcm = mock.MagicMock(spec=LifecycleManager)
    service._lcm.project_info = mock.MagicMock(spec=ProjectInfo)
    service._lcm.project_info.get_project_var = lambda _: "foo"

    # Installation of repositories in the build instance
    mock_install = mocker.patch(
        "craft_application.util.repositories.install_package_repositories"
    )
    # Installation of repositories in overlays
    mock_callback = mocker.patch.object(
        craft_parts.callbacks, "register_configure_overlay"
    )

    service.run("prime")

    mock_install.assert_called_once_with(
        fake_repositories, service._lcm, local_keys_path=local_keys_path
    )
    mock_callback.assert_called_once_with(repositories.install_overlay_repositories)


def test_lifecycle_project_variables(
    app_metadata, fake_services, tmp_path, fake_platform
):
    """Test that project variables are set after the lifecycle runs."""
    fake_services.get("build_plan").set_platforms(fake_platform)
    skip_if_build_plan_empty(fake_services.get("build_plan"))

    class LocalProject(models.Project):
        color: str | None = None

    fake_project = LocalProject.unmarshal(
        {
            "name": "project",
            "base": "ubuntu@24.04",
            "version": "1.0.0.post64+git12345678",
            "parts": {"my-part": {"plugin": "nil"}},
            "platforms": {"arm64": None},
            "adopt-info": "my-part",
        }
    )
    work_dir = tmp_path / "work"
    app_metadata = dataclasses.replace(
        app_metadata, project_variables=["version", "color"], ProjectClass=LocalProject
    )

    service = lifecycle.LifecycleService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=work_dir,
        cache_dir=tmp_path / "cache",
        platform=None,
    )
    service._project = fake_project
    service._lcm = mock.MagicMock(spec=LifecycleManager)
    service._lcm.project_info = mock.MagicMock(spec=ProjectInfo)
    service._lcm.project_info.get_project_var = lambda _: "foo"

    service.run("prime")

    assert service.project_info.get_project_var("version") == "foo"
    assert service.project_info.get_project_var("color") == "foo"


def test_no_builds_error(mocker, fake_parts_lifecycle, fake_services):
    """Build plan has no items."""
    mock_plan = mocker.patch.object(
        fake_services.get("build_plan"), "plan", return_value=[]
    )

    with pytest.raises(errors.EmptyBuildPlanError):
        fake_parts_lifecycle.run("prime")

    mock_plan.assert_called_once_with()


def test_multiple_builds_error(
    fake_parts_lifecycle, fake_services, fake_host_architecture
):
    """Build plan contains more than 1 item."""
    if len(fake_services.get("build_plan").plan()) <= 1:
        pytest.skip(reason="Architecture has 0 or 1 builds")
    with pytest.raises(errors.MultipleBuildsError) as e:
        fake_parts_lifecycle._validate_build_plan()
    assert str(e.value).startswith("Multiple builds match the current platform: ")


@pytest.mark.parametrize(
    ("base", "expected_pretty"),
    [
        (craft_platforms.DistroBase("ubuntu", "22.04"), "Ubuntu 22.04"),
        (craft_platforms.DistroBase("centos", "6"), "Centos 6"),
        (craft_platforms.DistroBase("centos", "devel"), "Centos devel"),
    ],
)
def test_invalid_base_error(
    build_plan_service,
    fake_parts_lifecycle,
    mocker,
    base,
    expected_pretty,
):
    """BuildInfo has a different base than the running environment."""
    fake_host = craft_platforms.DistroBase(distribution="ubuntu", series="24.04")
    fake_build = craft_platforms.BuildInfo(
        platform="anything",
        build_on=craft_platforms.DebianArchitecture.from_host(),
        build_for=craft_platforms.DebianArchitecture.from_host(),
        build_base=base,
    )
    mocker.patch.object(
        craft_platforms.DistroBase,
        "from_linux_distribution",
        return_value=fake_host,
    )
    mocker.patch.object(build_plan_service, "plan", return_value=[fake_build])

    expected = (
        f"{expected_pretty} builds cannot be performed on this Ubuntu 24.04 system."
    )

    with pytest.raises(errors.IncompatibleBaseError, match=expected):
        fake_parts_lifecycle.run("prime")


def test_devel_base_no_error(fake_parts_lifecycle, build_plan_service, mocker):
    """BuildInfo has a 'devel' build-base but the system is the same."""
    fake_base = craft_platforms.DistroBase("ubuntu", "24.04")
    mocker.patch.object(
        craft_platforms.DistroBase,
        "from_linux_distribution",
        return_value=fake_base,
    )
    fake_build = craft_platforms.BuildInfo(
        platform="anything",
        build_on=craft_platforms.DebianArchitecture.from_host(),
        build_for=craft_platforms.DebianArchitecture.from_host(),
        build_base=fake_base,
    )
    mocker.patch.object(build_plan_service, "plan", return_value=[fake_build])

    # Pass None as the step to ensure validation but skip the actual lifecycle run
    _ = fake_parts_lifecycle.run(None)
