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
from craft_parts import Action, ActionType, Features, LifecycleManager, PartsError, Step

from craft_application import errors
from craft_application.services import base

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path

    from craft_application.app import AppMetadata
    from craft_application.models import Project


ACTION_MESSAGES = types.MappingProxyType(
    {
        Step.PULL: types.MappingProxyType(
            {
                ActionType.RUN: "pull",
                ActionType.RERUN: "repull",
                ActionType.SKIP: "skip pull",
                ActionType.UPDATE: "update sources for",
            }
        ),
        Step.OVERLAY: types.MappingProxyType(
            {
                ActionType.RUN: "overlay",
                ActionType.RERUN: "re-overlay",
                ActionType.SKIP: "skip overlay",
                ActionType.UPDATE: "update overlay for",
                ActionType.REAPPLY: "reapply",
            }
        ),
        Step.BUILD: types.MappingProxyType(
            {
                ActionType.RUN: "build",
                ActionType.RERUN: "rebuild",
                ActionType.SKIP: "skip build",
                ActionType.UPDATE: "update build for",
            }
        ),
        Step.STAGE: types.MappingProxyType(
            {
                ActionType.RUN: "stage",
                ActionType.RERUN: "restage",
                ActionType.SKIP: "skip stage",
            }
        ),
        Step.PRIME: types.MappingProxyType(
            {
                ActionType.RUN: "prime",
                ActionType.RERUN: "re-prime",
                ActionType.SKIP: "skip prime",
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


class LifecycleService(base.BaseService):
    """Create and manage the parts lifecycle.

    :param app: An AppMetadata object containing metadata about the application.
    :param project: The Project object that describes this project.
    :param work_dir: The working directory for parts processing.
    :param lifecycle_kwargs: Additional keyword arguments are passed through to the
        LifecycleManager on initialisation.
    """

    def __init__(
        self,
        app: AppMetadata,
        project: Project,
        *,
        work_dir: Path | str,
        cache_dir: Path | str,
        **lifecycle_kwargs: Any,  # noqa: ANN401 - eventually used in an Any
    ) -> None:
        super().__init__(app, project)
        self._work_dir = work_dir
        self._cache_dir = cache_dir
        self._manager_kwargs = lifecycle_kwargs
        self._lcm = self._init_lifecycle_manager()

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
                cache_dir=self._cache_dir,
                work_dir=self._work_dir,
                base=self._project.effective_base,
                ignore_local_sources=self._app.source_ignore_patterns,
                **self._manager_kwargs,
            )
        except PartsError as err:
            raise errors.PartsLifecycleError.from_parts_error(err) from err

    @property
    def prime_dir(self) -> Path:
        """The path to the prime directory."""
        return self._lcm.project_info.dirs.prime_dir

    def run(self, step_name: str, part_names: list[str] | None = None) -> None:
        """Run the lifecycle manager for the parts."""
        target_step = _get_step(step_name)

        try:
            emit.trace(f"Planning {step_name} for {part_names or 'all parts'}")
            actions = self._lcm.plan(target_step, part_names=part_names)
            with self._lcm.action_executor() as aex:
                for action in actions:
                    message = _get_parts_action_message(action)
                    emit.progress(f"Executing parts lifecycle: {message}")
                    with emit.open_stream("Executing action") as stream:
                        aex.execute(action, stdout=stream, stderr=stream)
                    emit.progress(f"Executed: {message}", permanent=True)

                emit.progress("Executed parts lifecycle", permanent=True)
        except RuntimeError as err:
            raise RuntimeError(f"Parts processing internal error: {err}") from err
        except OSError as err:
            raise errors.PartsLifecycleError.from_os_error(err) from err
        except Exception as err:  # noqa: BLE001 - Converting general error.
            raise errors.PartsLifecycleError(f"Unknown error: {str(err)}") from err

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

    def __repr__(self) -> str:
        work_dir = self._work_dir
        cache_dir = self._cache_dir
        return (
            f"{self.__class__.__name__}({self._app!r}, {self._project!r}, "
            f"{work_dir=}, {cache_dir=}, **{self._manager_kwargs!r})"
        )
