# This file is part of craft-application.
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
"""craft-parts lifecycle integration."""

from __future__ import annotations

import contextlib
import types
from pathlib import Path
from typing import TYPE_CHECKING, Any

import craft_platforms
import distro
from craft_cli import emit
from craft_parts import (
    Action,
    ActionType,
    Features,
    LifecycleManager,
    PartsError,
    ProjectInfo,
    Step,
    StepInfo,
    callbacks,
)
from craft_parts.errors import CallbackRegistrationError
from typing_extensions import override

from craft_application import errors, models, util
from craft_application.services import base
from craft_application.util import repositories

if TYPE_CHECKING:  # pragma: no cover
    from craft_application.application import AppMetadata
    from craft_application.services import ServiceFactory


ACTION_MESSAGES = types.MappingProxyType(
    {
        Step.PULL: types.MappingProxyType(
            {
                ActionType.RUN: "Pulling",
                ActionType.RERUN: "Repulling",
                ActionType.SKIP: "Skipping pull for",
                ActionType.UPDATE: "Updating sources for",
            }
        ),
        Step.OVERLAY: types.MappingProxyType(
            {
                ActionType.RUN: "Overlaying",
                ActionType.RERUN: "Re-overlaying",
                ActionType.SKIP: "Skipping overlay for",
                ActionType.UPDATE: "Updating overlay for",
                ActionType.REAPPLY: "Reapplying",
            }
        ),
        Step.BUILD: types.MappingProxyType(
            {
                ActionType.RUN: "Building",
                ActionType.RERUN: "Rebuilding",
                ActionType.SKIP: "Skipping build for",
                ActionType.UPDATE: "Updating build for",
            }
        ),
        Step.STAGE: types.MappingProxyType(
            {
                ActionType.RUN: "Staging",
                ActionType.RERUN: "Restaging",
                ActionType.SKIP: "Skipping stage for",
            }
        ),
        Step.PRIME: types.MappingProxyType(
            {
                ActionType.RUN: "Priming",
                ActionType.RERUN: "Repriming",
                ActionType.SKIP: "Skipping prime for",
            }
        ),
    }
)


def _get_parts_action_message(action: Action) -> str:
    """Get a user-readable message for a particular craft-parts action."""
    message = f"{ACTION_MESSAGES[action.step][action.action_type]} {action.part_name}"
    if action.reason:
        return message + f" ({action.reason})"
    return message


def _get_step(step_name: str) -> Step:
    """Get a lifecycle step by name."""
    if step_name.lower() == "overlay" and not Features().enable_overlay:
        raise RuntimeError("Invalid target step 'overlay'")
    steps = Step.__members__
    try:
        return steps[step_name.upper()]
    except KeyError:
        raise RuntimeError(f"Invalid target step {step_name!r}") from None


class LifecycleService(base.AppService):
    """Create and manage the parts lifecycle.

    :param app: An AppMetadata object containing metadata about the application.
    :param project: The Project object that describes this project.
    :param work_dir: The working directory for parts processing.
    :param cache_dir: The cache directory for parts processing.
    :param build_plan: The filtered build plan of platforms that are valid for
        the running host.
    :param lifecycle_kwargs: Additional keyword arguments are passed through to the
        LifecycleManager on initialisation.
    """

    _project: models.Project

    def __init__(
        self,
        app: AppMetadata,
        services: ServiceFactory,
        *,
        work_dir: Path | str,
        cache_dir: Path | str,
        **lifecycle_kwargs: Any,
    ) -> None:
        super().__init__(app, services)
        self._work_dir = work_dir
        self._cache_dir = cache_dir
        self._manager_kwargs = lifecycle_kwargs
        self._lcm: LifecycleManager = None  # type: ignore[assignment]

    @override
    def setup(self) -> None:
        """Initialize the LifecycleManager with previously-set arguments."""
        self._project = self._services.get("project").get()
        self._lcm = self._init_lifecycle_manager()
        callbacks.register_post_step(self.post_prime, step_list=[Step.PRIME])

    def _get_build(self) -> craft_platforms.BuildInfo:
        """Get the build for this run."""
        plan = self._services.get("build_plan").plan()
        if not plan:
            raise errors.EmptyBuildPlanError
        return plan[0]

    def _validate_build_plan(self) -> None:
        """Validate that the build plan is usable for a lifecycle run."""
        plan = self._services.get("build_plan").plan()
        match len(plan):
            case 0:
                raise errors.EmptyBuildPlanError
            case 1:
                build = plan[0]
            case _:
                raise errors.MultipleBuildsError(plan)

        host_base = craft_platforms.DistroBase.from_linux_distribution(
            distro.LinuxDistribution()
        )
        if build.build_base.series == "devel":
            # If the build base is "devel", we don't try to match the specific
            # version as that is a moving target; Just ensure the systems are the
            # same.
            if build.build_base.distribution != host_base.distribution:
                raise errors.IncompatibleBaseError(host_base, build.build_base)
        elif build.build_base != host_base:
            raise errors.IncompatibleBaseError(host_base, build.build_base)

    def _get_build_for(self) -> str:
        """Get the ``build_for`` architecture for craft-parts.

        The default behaviour is as follows:
        1. If the build plan's ``build_for`` is ``all``, use the host architecture.
        2. If it's anything else, use that.
        3. If it's undefined, use the host architecture.
        """
        # Note: we fallback to the host's architecture here if the build plan
        # is empty just to be able to create the LifecycleManager; this will
        # correctly fail later on when run() is called (but not necessarily when
        # something else like clean() is called).
        # We also use the host arch if the build-for is 'all'
        try:
            build = self._get_build()
        except errors.EmptyBuildPlanError:
            return util.get_host_architecture()
        if build.build_for != "all":
            return str(build.build_for)
        return util.get_host_architecture()

    def _init_lifecycle_manager(self) -> LifecycleManager:
        """Create and return the Lifecycle manager.

        An application may override this method if needed if the lifecycle
        manager needs to be called differently.
        """
        emit.debug(f"Initialising lifecycle manager in {self._work_dir}")
        emit.trace(f"Lifecycle: {repr(self)}")

        build_for = self._get_build_for()

        if self._project.package_repositories:
            self._manager_kwargs["package_repositories"] = (
                self._project.package_repositories
            )

        pvars: dict[str, str] = {}
        for var in self._app.project_variables:
            pvars[var] = getattr(self._project, var) or ""
        self._project_vars = pvars

        emit.debug(f"Project vars: {self._project_vars}")
        emit.debug(f"Adopting part: {self._project.adopt_info}")

        source_ignore_patterns = [
            *self._app.source_ignore_patterns,
        ]

        if Path("spread/.extension").exists():
            # Ignore spread.yaml and spread to prevent repulling sources
            # when test files are changed.
            source_ignore_patterns.extend(["spread.yaml", "spread"])

        try:
            return LifecycleManager(
                {"parts": self._project.parts},
                application_name=self._app.name,
                arch=build_for,
                cache_dir=self._cache_dir,
                work_dir=self._work_dir,
                ignore_local_sources=source_ignore_patterns,
                parallel_build_count=util.get_parallel_build_count(self._app.name),
                project_vars_part_name=self._project.adopt_info,
                project_vars=self._project_vars,
                track_stage_packages=True,
                partitions=self._services.get("project").partitions,
                **self._manager_kwargs,
            )
        except PartsError as err:
            raise errors.PartsLifecycleError.from_parts_error(err) from err

    @property
    def prime_dir(self) -> Path:
        """The path to the prime directory."""
        return self._lcm.project_info.dirs.prime_dir

    @property
    def project_info(self) -> ProjectInfo:
        """The lifecycle's ProjectInfo."""
        return self._lcm.project_info

    def get_pull_assets(self, *, part_name: str) -> dict[str, Any] | None:
        """Obtain the part's pull state assets.

        :param part_name: The name of the part to get assets from.
        :return: The dictionary of the part's pull assets, or None if no state found.
        """
        return self._lcm.get_pull_assets(part_name=part_name)

    def get_primed_stage_packages(self, *, part_name: str) -> list[str] | None:
        """Obtain the list of primed stage packages.

        :param part_name: The name of the part to get primed stage packages from.
        :return: The sorted list of primed stage packages, or None if no state found.
        """
        return self._lcm.get_primed_stage_packages(part_name=part_name)

    def run(self, step_name: str | None, part_names: list[str] | None = None) -> None:
        """Run the lifecycle manager for the parts."""
        target_step = _get_step(step_name) if step_name else None

        self._validate_build_plan()

        try:
            if self._project.package_repositories:
                emit.trace("Installing package repositories")
                repositories.install_package_repositories(
                    self._project.package_repositories,
                    self._lcm,
                    local_keys_path=self._get_local_keys_path(),
                )
                with contextlib.suppress(CallbackRegistrationError):
                    callbacks.register_configure_overlay(
                        repositories.install_overlay_repositories
                    )
            if target_step:
                emit.trace(f"Planning {step_name} for {part_names or 'all parts'}")
                actions = self._lcm.plan(target_step, part_names=part_names)
            else:
                actions = []

            emit.progress("Initialising lifecycle")
            with self._lcm.action_executor() as aex:
                for action in actions:
                    message = _get_parts_action_message(action)
                    emit.progress(message)
                    with emit.open_stream() as stream:
                        aex.execute(action, stdout=stream, stderr=stream)

        except PartsError as err:
            raise errors.PartsLifecycleError.from_parts_error(err) from err
        except RuntimeError as err:
            raise RuntimeError(f"Parts processing internal error: {err}") from err
        except OSError as err:
            raise errors.PartsLifecycleError.from_os_error(err) from err
        except Exception as err:
            raise errors.PartsLifecycleError(f"Unknown error: {str(err)}") from err

    def post_prime(self, step_info: StepInfo) -> bool:
        """Perform any necessary post-lifecycle modifications to the prime directory.

        This method should be idempotent and meet the requirements for a craft-parts
        callback. It is added as a post-prime callback during the setup phase.

        NOTE: This is not guaranteed to run in any particular order if other callbacks
        are added to the prime step.
        """
        if step_info.step != Step.PRIME:
            raise RuntimeError(f"Post-prime hook called after step: {step_info.step}")
        return False

    def clean(self, part_names: list[str] | None = None) -> None:
        """Remove lifecycle artifacts.

        :param part_names: The names of the parts to clean. If unspecified, all parts
            will be cleaned.
        """
        if part_names:
            message = "Cleaning parts: " + ", ".join(part_names)
        else:
            message = "Cleaning all parts"

        emit.progress(message)
        self._lcm.clean(part_names=part_names)

    @staticmethod
    def previous_step_name(step_name: str) -> str | None:
        """Get the name of the step immediately previous to `step_name`.

        Returns None if `step_name` is the first one (pull).
        """
        step = _get_step(step_name)
        previous_steps = step.previous_steps()
        return previous_steps[-1].name.lower() if previous_steps else None

    def __repr__(self) -> str:
        work_dir = self._work_dir
        cache_dir = self._cache_dir
        return (
            f"{self.__class__.__name__}({self._app!r}, "
            f"{work_dir=}, {cache_dir=}, **{self._manager_kwargs!r})"
        )

    def _get_local_keys_path(self) -> Path | None:
        """Return a directory with public keys for package-repositories.

        This default implementation does not support local keys; it should be
        overridden by subclasses that do.
        """
        return None
