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
from unittest import mock

import craft_parts
import craft_parts.callbacks
import pytest
import pytest_check
from craft_application import errors, models, util
from craft_application.errors import InvalidParameterError, PartsLifecycleError
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
from craft_providers import bases


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


@pytest.fixture()
def fake_parts_lifecycle(
    app_metadata, fake_project, fake_services, tmp_path, fake_build_plan
):
    work_dir = tmp_path / "work"
    cache_dir = tmp_path / "cache"
    fake_service = FakePartsLifecycle(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=work_dir,
        cache_dir=cache_dir,
        build_plan=fake_build_plan,
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

    assert actual == message, "Unexpected %r" % actual


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

    assert actual == message, "Unexpected %r" % actual


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

    assert actual == message, "Unexpected %r" % actual


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

    assert actual == message, "Unexpected %r" % actual


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

    assert actual == message, "Unexpected %r" % actual


def test_progress_messages(fake_parts_lifecycle, emitter):
    actions = [
        Action("my-part", Step.PULL),
        Action("my-part", Step.BUILD),
        Action("my-part", Step.OVERLAY),
        Action("my-part", Step.STAGE),
        Action("my-part", Step.PRIME),
    ]

    lcm = fake_parts_lifecycle._lcm
    lcm.plan.return_value = actions

    fake_parts_lifecycle.run("prime", "arch")

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
def test_init_success(
    app_metadata, fake_project, fake_services, tmp_path, fake_build_plan
):
    service = lifecycle.LifecycleService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=tmp_path,
        cache_dir=tmp_path,
        platform=None,
        build_plan=fake_build_plan,
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
    tmp_path,
    error,
    expected,
    fake_build_plan,
):
    mock_lifecycle = mock.Mock(side_effect=error)
    monkeypatch.setattr(lifecycle, "LifecycleManager", mock_lifecycle)

    service = lifecycle.LifecycleService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=tmp_path,
        cache_dir=tmp_path,
        platform=None,
        build_plan=fake_build_plan,
    )

    with pytest.raises(type(expected)) as exc_info:
        service.setup()

    assert exc_info.value.args == expected.args


def test_init_with_feature_package_repositories(
    app_metadata, fake_project, fake_services, tmp_path, fake_build_plan
):
    package_repositories = [{"type": "apt", "ppa": "ppa/ppa"}]
    fake_project.package_repositories = package_repositories.copy()
    service = lifecycle.LifecycleService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=tmp_path,
        cache_dir=tmp_path,
        platform=None,
        build_plan=fake_build_plan,
    )
    assert service._lcm is None
    service.setup()
    assert service._lcm is not None
    assert service._lcm._project_info.package_repositories == package_repositories


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
    "actions",
    [
        [],
        [Action("my-part", Step.PULL), Action("my-part", Step.BUILD)],
    ],
)
def test_run_success(fake_parts_lifecycle, actions, check):
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


def test_run_no_step(fake_parts_lifecycle):
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
def test_run_failure(fake_parts_lifecycle, err, exc_class, message_regex):
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
    start = f"FakePartsLifecycle({app_metadata!r}, {fake_project!r}, "

    actual = repr(fake_parts_lifecycle)

    pytest_check.is_true(actual.startswith(start))
    pytest_check.is_true(
        re.fullmatch(
            r"FakePartsLifecycle\(.+, work_dir=(Posix|Windows)Path\('.+'\), "
            r"cache_dir=(Posix|Windows)Path\('.+'\), "
            r"plan=\[BuildInfo\(.+\)], \*\*{}\)",
            actual,
        )
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


# endregion
# region Feature package repositories tests


def test_lifecycle_package_repositories(
    app_metadata, fake_project, fake_services, tmp_path, mocker, fake_build_plan
):
    """Test that package repositories installation is called in the lifecycle."""
    fake_repositories = [{"type": "apt", "ppa": "ppa/ppa"}]
    fake_project.package_repositories = fake_repositories.copy()
    work_dir = tmp_path / "work"

    service = lifecycle.LifecycleService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=work_dir,
        cache_dir=tmp_path / "cache",
        platform=None,
        build_plan=fake_build_plan,
    )
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

    mock_install.assert_called_once_with(fake_repositories, service._lcm)
    mock_callback.assert_called_once_with(repositories.install_overlay_repositories)


# endregion

# region parallel build count tests


@pytest.mark.parametrize(
    ("env_dict", "cpu_count", "expected"),
    [
        (
            {},
            None,
            1,
        ),
        (
            {},
            100,
            100,
        ),
        (
            {"TESTCRAFT_PARALLEL_BUILD_COUNT": "100"},
            1,
            100,
        ),
        (
            {"CRAFT_PARALLEL_BUILD_COUNT": "200"},
            1,
            200,
        ),
        (
            {
                "TESTCRAFT_MAX_PARALLEL_BUILD_COUNT": "100",
            },
            50,
            50,
        ),
        (
            {
                "CRAFT_MAX_PARALLEL_BUILD_COUNT": "100",
            },
            80,
            80,
        ),
        (
            {
                "TESTCRAFT_PARALLEL_BUILD_COUNT": "100",
                "CRAFT_PARALLEL_BUILD_COUNT": "200",
            },
            1,
            100,
        ),
        (
            {
                "TESTCRAFT_MAX_PARALLEL_BUILD_COUNT": "100",
                "CRAFT_MAX_PARALLEL_BUILD_COUNT": "200",
            },
            150,
            100,
        ),
        (
            {
                "TESTCRAFT_MAX_PARALLEL_BUILD_COUNT": "100",
                "CRAFT_MAX_PARALLEL_BUILD_COUNT": "200",
            },
            None,
            1,
        ),
        (
            {
                "TESTCRAFT_PARALLEL_BUILD_COUNT": "100",
                "CRAFT_PARALLEL_BUILD_COUNT": "200",
                "TESTCRAFT_MAX_PARALLEL_BUILD_COUNT": "300",
                "CRAFT_MAX_PARALLEL_BUILD_COUNT": "400",
            },
            150,
            100,
        ),
    ],
)
def test_get_parallel_build_count(
    monkeypatch, mocker, fake_parts_lifecycle, env_dict, cpu_count, expected
):
    mocker.patch("os.cpu_count", return_value=cpu_count)
    for env_dict_key, env_dict_value in env_dict.items():
        monkeypatch.setenv(env_dict_key, env_dict_value)

    assert fake_parts_lifecycle._get_parallel_build_count() == expected


@pytest.mark.parametrize(
    ("env_dict", "cpu_count"),
    [
        (
            {
                "TESTCRAFT_PARALLEL_BUILD_COUNT": "abc",
            },
            1,
        ),
        (
            {
                "CRAFT_PARALLEL_BUILD_COUNT": "-",
            },
            1,
        ),
        (
            {
                "TESTCRAFT_MAX_PARALLEL_BUILD_COUNT": "*",
            },
            1,
        ),
        (
            {
                "CRAFT_MAX_PARALLEL_BUILD_COUNT": "$COUNT",
            },
            1,
        ),
        (
            {
                "TESTCRAFT_PARALLEL_BUILD_COUNT": "0",
            },
            1,
        ),
        (
            {
                "CRAFT_PARALLEL_BUILD_COUNT": "-1",
            },
            1,
        ),
        (
            {
                "TESTCRAFT_MAX_PARALLEL_BUILD_COUNT": "5.6",
            },
            1,
        ),
        (
            {
                "CRAFT_MAX_PARALLEL_BUILD_COUNT": "inf",
            },
            1,
        ),
    ],
)
def test_get_parallel_build_count_error(
    monkeypatch, mocker, fake_parts_lifecycle, env_dict, cpu_count
):
    mocker.patch("os.cpu_count", return_value=cpu_count)
    for env_dict_key, env_dict_value in env_dict.items():
        monkeypatch.setenv(env_dict_key, env_dict_value)

    with pytest.raises(
        InvalidParameterError, match=r"^Value '.*' is invalid for parameter '.*'.$"
    ):
        fake_parts_lifecycle._get_parallel_build_count()


# endregion

# region project variables


def test_lifecycle_project_variables(
    app_metadata, fake_services, tmp_path, fake_build_plan
):
    """Test that project variables are set after the lifecycle runs."""

    class LocalProject(models.Project):
        color: str | None

    fake_project = LocalProject.unmarshal(
        {
            "name": "project",
            "base": "core24",
            "version": "1.0.0.post64+git12345678",
            "parts": {"my-part": {"plugin": "nil"}},
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
        build_plan=fake_build_plan,
    )
    service._lcm = mock.MagicMock(spec=LifecycleManager)
    service._lcm.project_info = mock.MagicMock(spec=ProjectInfo)
    service._lcm.project_info.get_project_var = lambda _: "foo"

    service.run("prime")

    assert service.project_info.get_project_var("version") == "foo"
    assert service.project_info.get_project_var("color") == "foo"


# endregion


@pytest.mark.parametrize("fake_build_plan", [0], indirect=True)
def test_no_builds_error(fake_parts_lifecycle):
    """Build plan has no items."""
    with pytest.raises(errors.EmptyBuildPlanError):
        fake_parts_lifecycle.run("prime")


@pytest.mark.parametrize("fake_build_plan", [2, 3, 4], indirect=True)
def test_multiple_builds_error(fake_parts_lifecycle):
    """Build plan contains more than 1 item."""
    with pytest.raises(errors.MultipleBuildsError):
        fake_parts_lifecycle.run("prime")


@pytest.mark.parametrize(
    ("system_name", "system_version", "expected_pretty"),
    [
        ("ubuntu", "22.04", "Ubuntu 22.04"),
        ("centos", "6", "Centos 6"),
        ("centos", "devel", "Centos devel"),
    ],
)
@pytest.mark.parametrize("fake_build_plan", [1], indirect=True)
def test_invalid_base_error(
    fake_parts_lifecycle,
    fake_build_plan,
    mocker,
    system_name,
    system_version,
    expected_pretty,
):
    """BuildInfo has a different base than the running environment."""
    fake_host = bases.BaseName(name="ubuntu", version="24.04")
    mocker.patch.object(
        util,
        "get_host_base",
        return_value=fake_host,
    )
    fake_build_plan[0].base = bases.BaseName(name=system_name, version=system_version)

    expected = (
        f"{expected_pretty} builds cannot be performed on this Ubuntu 24.04 system."
    )

    with pytest.raises(errors.IncompatibleBaseError, match=expected):
        fake_parts_lifecycle.run("prime")


@pytest.mark.parametrize("fake_build_plan", [1], indirect=True)
def test_devel_base_no_error(fake_parts_lifecycle, fake_build_plan, mocker):
    """BuildInfo has a 'devel' build-base but the system is the same."""
    fake_host = bases.BaseName(name="ubuntu", version="24.04")
    mocker.patch.object(
        util,
        "get_host_base",
        return_value=fake_host,
    )
    fake_build_plan[0].base = bases.BaseName(name="ubuntu", version="devel")

    # Pass None as the step to ensure validation but skip the actual lifecycle run
    _ = fake_parts_lifecycle.run(None)
