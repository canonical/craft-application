# This file is part of craft-application.
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
"""craft-parts lifecycle integration."""
from __future__ import annotations

import types
from typing import TYPE_CHECKING, Any

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
from typing_extensions import override

from craft_application import errors
from craft_application.services import base
from craft_application.util import convert_architecture_deb_to_platform

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from craft_application.application import AppMetadata
    from craft_application.models import Project
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


class LifecycleService(base.ProjectService):
    """Create and manage the parts lifecycle.

    :param app: An AppMetadata object containing metadata about the application.
    :param project: The Project object that describes this project.
    :param work_dir: The working directory for parts processing.
    :param cache_dir: The cache directory for parts processing.
    :param build_for: The architecture or platform we are building for.
    :param lifecycle_kwargs: Additional keyword arguments are passed through to the
        LifecycleManager on initialisation.
    """

    def __init__(  # noqa: PLR0913 (too many arguments)
        self,
        app: AppMetadata,
        services: ServiceFactory,
        *,
        project: Project,
        work_dir: Path | str,
        cache_dir: Path | str,
        build_for: str,
        **lifecycle_kwargs: Any,  # noqa: ANN401 - eventually used in an Any
    ) -> None:
        super().__init__(app, services, project=project)
        self._work_dir = work_dir
        self._cache_dir = cache_dir
        self._build_for = build_for
        self._manager_kwargs = lifecycle_kwargs
        self._lcm: LifecycleManager = None  # type: ignore[assignment]

    @override
    def setup(self) -> None:
        """Initialize the LifecycleManager with previously-set arguments."""
        self._lcm = self._init_lifecycle_manager()
        callbacks.register_post_step(self.post_prime, step_list=[Step.PRIME])

    def _init_lifecycle_manager(self) -> LifecycleManager:
        """Create and return the Lifecycle manager.

        An application may override this method if needed if the lifecycle
        manager needs to be called differently.
        """
        emit.debug(f"Initialising lifecycle manager in {self._work_dir}")
        emit.trace(f"Lifecycle: {repr(self)}")
        try:
            return LifecycleManager(
                {"parts": self._project.parts},
                application_name=self._app.name,
                arch=convert_architecture_deb_to_platform(self._build_for),
                cache_dir=self._cache_dir,
                work_dir=self._work_dir,
                ignore_local_sources=self._app.source_ignore_patterns,
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

    def run(self, step_name: str | None, part_names: list[str] | None = None) -> None:
        """Run the lifecycle manager for the parts."""
        target_step = _get_step(step_name) if step_name else None

        try:
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
        except Exception as err:  # noqa: BLE001 - Converting general error.
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
        build_for = self._build_for
        return (
            f"{self.__class__.__name__}({self._app!r}, {self._project!r}, "
            f"{work_dir=}, {cache_dir=}, {build_for=}, **{self._manager_kwargs!r})"
        )
