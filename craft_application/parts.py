from craft_parts.features import Features
from craft_parts import ActionType, Step
import craft_parts
from . import errors
from pathlib import Path
from craft_cli import emit
from typing import Dict, Optional, List
from functools import cached_property


def _get_lifecycle_steps() -> Dict[str, Step]:
    lifecycle_steps = {
        "pull": Step.PULL,
        "overlay": Step.OVERLAY,
        "build": Step.BUILD,
        "stage": Step.STAGE,
        "prime": Step.PRIME,
    }

    if not Features.enable_overlay:
        del lifecycle_steps["overlay"]

    return lifecycle_steps


class PartsLifecycle:
    """Create and manage the parts lifecycle.
    :param all_parts: A dictionary containing the parts defined in the project.
    :param work_dir: The working directory for parts processing.
    :raises PartsLifecycleError: On error initializing the parts lifecycle.
    """

    def __init__(
        self,
        all_parts,
        *,
        cache_dir: str,
        work_dir: Path,
        base: str,
    ) -> None:
        self._lifecycle_steps = _get_lifecycle_steps()
        self._cache_dir = cache_dir
        self._all_parts = all_parts
        self._work_dir = work_dir
        self._base = base

    @property
    def _all_part_names(self):
        return [*self._all_parts]

    @cached_property
    def _lcm(self) -> craft_parts.LifecycleManager:
        """Lifecycle Manager instance.

        It is lazy loaded to be easily overridable.
        """
        try:
            return craft_parts.LifecycleManager(
                {"parts": self._all_parts},
                application_name="snapcraft",
                work_dir=self._work_dir,
                cache_dir=self._cache_dir,
                base=self._base,
                ignore_local_sources=["*.snap"],
            )
        except craft_parts.PartsError as err:
            raise errors.PartsLifecycleError(str(err)) from err

    def run(self, step_name: str, part_names: Optional[List[str]]) -> None:
        try:
            target_step = self._lifecycle_steps[step_name]
        except KeyError as key_error:
            raise RuntimeError(f"Invalid target step {step_name!r}") from key_error

        try:
            if step_name:
                actions = self._lcm.plan(target_step, part_names=part_names)
            else:
                actions = []

            with self._lcm.action_executor() as aex:
                for action in actions:
                    message = _action_message(action)
                    emit.progress(f"Executing parts lifecycle: {message}")
                    with emit.open_stream("Executing action") as stream:
                        aex.execute(action, stdout=stream, stderr=stream)
                    emit.progress(f"Executed: {message}", permanent=True)

                emit.progress("Executed parts lifecycle", permanent=True)
        except RuntimeError as err:
            raise RuntimeError(f"Parts processing internal error: {err}") from err
        except OSError as err:
            msg = err.strerror
            if err.filename:
                msg = f"{err.filename}: {msg}"
            raise errors.PartsLifecycleError(msg) from err
        except Exception as err:
            raise errors.PartsLifecycleError(str(err)) from err


def _action_message(action: craft_parts.Action) -> str:
    msg = {
        Step.PULL: {
            ActionType.RUN: "pull",
            ActionType.RERUN: "repull",
            ActionType.SKIP: "skip pull",
            ActionType.UPDATE: "update sources for",
        },
        Step.OVERLAY: {
            ActionType.RUN: "overlay",
            ActionType.RERUN: "re-overlay",
            ActionType.SKIP: "skip overlay",
            ActionType.UPDATE: "update overlay for",
            ActionType.REAPPLY: "reapply",
        },
        Step.BUILD: {
            ActionType.RUN: "build",
            ActionType.RERUN: "rebuild",
            ActionType.SKIP: "skip build",
            ActionType.UPDATE: "update build for",
        },
        Step.STAGE: {
            ActionType.RUN: "stage",
            ActionType.RERUN: "restage",
            ActionType.SKIP: "skip stage",
        },
        Step.PRIME: {
            ActionType.RUN: "prime",
            ActionType.RERUN: "re-prime",
            ActionType.SKIP: "skip prime",
        },
    }

    message = f"{msg[action.step][action.action_type]} {action.part_name}"

    if action.reason:
        message += f" ({action.reason})"

    return message
