#  This file is part of craft-application.
#
# Copyright 2023 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Main application class for a craft application."""
import abc
import contextlib
import functools
import os
import pathlib
import signal
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Generator, List, Optional, Type, cast

from craft_cli import (
    ArgumentParsingError,
    BaseCommand,
    CommandGroup,
    CraftError,
    Dispatcher,
    EmitterMode,
    GlobalArgument,
    ProvideHelpException,
    emit,
)
from craft_providers import Executor, ProviderError
from xdg import BaseDirectory

from .commands.base import AppCommand
from .commands.lifecycle import get_lifecycle_command_group
from .parts import PartsLifecycle
from .project import Project
from .provider import ProviderManager

GLOBAL_VERSION = GlobalArgument(
    "version", "flag", "-V", "--version", "Show the application version and exit"
)

if TYPE_CHECKING:
    pass


class Application(metaclass=abc.ABCMeta):
    """Craft Application Builder.

    :ivar name: application name
    :ivar version: application version
    """

    def __init__(  # noqa PLR0913 - Can't determine how to reduce arguments.
        self,
        name: str,
        version: str,
        summary: str,
        manager: ProviderManager,
        project_class: Type[Project] = Project,
    ) -> None:
        """Initialize an Application.

        :param name: application name
        :param version: application version
        :param summary: application summary
        :param manager: a ProviderManager for handling managed mode.
        :param project_class: The class to use for creating a Project instance.
        """
        self.name = name
        self.version = version
        self._summary = summary
        self._project_class = project_class
        self._command_groups: List[CommandGroup] = []
        self._global_arguments: List[GlobalArgument] = [GLOBAL_VERSION]
        self._manager = manager

    def _get_command_groups(self) -> List[CommandGroup]:
        """Return command groups."""
        lifecycle_commands = get_lifecycle_command_group()

        return [lifecycle_commands, *self._command_groups]

    @property
    def log_path(self) -> Optional[Path]:
        """Get the path to the managed log file if managed, None otherwise."""
        if self._manager.is_managed:
            return self.managed_log_path
        return None

    @property
    def managed_log_path(self) -> Path:
        """Get the location of the managed instance's log file."""
        return Path(
            f"/tmp/{self.name}.log"  # noqa S108 - only applies inside managed instance.
        )

    def add_global_argument(self, argument: GlobalArgument) -> None:
        """Add a global argument to the Application."""
        self._global_arguments.append(argument)

    def add_command_group(self, name: str, commands: List[BaseCommand]) -> None:
        """Add a CommandGroup to the Application."""
        self._command_groups.append(CommandGroup(name, commands))

    @property
    def cache_dir(self) -> str:
        """Get the directory for caching any data."""
        # Ignoring output from xdg module until we get a typeshed item.
        return cast(str, BaseDirectory.save_cache_path(self.name))

    @functools.cached_property
    def parts_lifecycle(self) -> PartsLifecycle:
        """Get the parts lifecycle for this application."""
        return PartsLifecycle(
            self.project.parts,
            cache_dir=self.cache_dir,
            work_dir=Path.cwd(),
            base=self.project.effective_base,
        )

    @functools.cached_property
    def project(self) -> Project:
        """Get this application's Project metadata."""
        project_file = Path(f"{self.name}.yaml").resolve()
        return self._project_class.from_file(project_file)

    def run_part_step(self, step_name: str, part_names: List[str]) -> None:
        """Run the parts lifecycle."""
        self.parts_lifecycle.run(step_name, part_names=part_names)

    def clean(self, *, part_names: List[str]) -> None:
        """Run the cleaner for the parts lifecycle."""
        self.parts_lifecycle.clean(part_names=part_names)

    @abc.abstractmethod
    def generate_metadata(self) -> None:
        """Generate the metadata in the prime directory for the Application."""

    @abc.abstractmethod
    def create_package(self) -> Path:
        """Create the final package from the prime directory.

        :returns: Path to created package.
        """

    @contextlib.contextmanager
    def managed_instance(
        self, instance_path: pathlib.PosixPath
    ) -> Generator[Executor, None, None]:
        """Run the application in managed mode."""
        provider = self._manager.get_provider()
        project_path = Path().resolve()
        inode_number = project_path.stat().st_ino
        instance_name = f"{self.name}-{self.project.name}-{inode_number}"
        base_configuration = self._manager.get_configuration(
            base=self.project.effective_base,
            instance_name=instance_name,
        )

        emit.progress("Launching managed instance...")
        with provider.launched_environment(
            project_name=self.project.name,
            project_path=project_path,
            base_configuration=base_configuration,
            instance_name=instance_name,
            # craft_parts.Base doesn't currently define an alias, but it's always there.
            build_base=base_configuration.alias.value,  # type: ignore[attr-defined]
            allow_unstable=True,
        ) as instance:
            try:
                with emit.pause():
                    instance.mount(host_source=project_path, target=instance_path)
                    yield instance
            finally:
                with instance.temporarily_pull_file(
                    source=self.managed_log_path, missing_ok=True
                ) as log_path:
                    if log_path:
                        emit.debug("Logs retrieved from managed instance:")
                        with log_path.open() as log_file:
                            for line in log_file:
                                emit.debug(":: " + line.rstrip())
                    else:
                        emit.debug("Could not find log file in instance.")

    def run_managed(self) -> None:
        """Run the application in a managed instance."""
        instance_path = pathlib.PosixPath("/root/project")
        with self.managed_instance(instance_path) as instance:
            try:
                instance.execute_run(
                    [self.name, *sys.argv[1:]], cwd=instance_path, check=True
                )
            except subprocess.CalledProcessError as exc:
                raise ProviderError(
                    f"Failed to execute {self.name} in instance."
                ) from exc

    def run(self) -> int:
        """Bootstrap and run the application."""
        emit.init(
            mode=EmitterMode.BRIEF,
            appname=self.name,
            greeting=f"Starting {self.name}",
            log_filepath=self.log_path,
        )

        dispatcher = Dispatcher(
            self.name,
            self._get_command_groups(),
            summary=self._summary,
            extra_global_args=self._global_arguments,
        )

        retcode = 1
        try:
            global_args = dispatcher.pre_parse_args(sys.argv[1:])
            if global_args.get("version"):
                emit.message(f"{self.name} {self.version}")
                emit.ended_ok()
                return 0

            command = cast(
                AppCommand,
                dispatcher.load_command(
                    {
                        "name": self.name,
                        "manager": self._manager,
                        "run_part_step": self.run_part_step,
                        "generate_metadata": self.generate_metadata,
                        "create_package": self.create_package,
                        "clean": self.clean,
                    }
                ),
            )
            if self._manager.is_managed or not command.is_managed:
                retcode = dispatcher.run() or 0
            else:
                self.run_managed()
                retcode = 0
        except ProvideHelpException as err:
            print(err, file=sys.stderr)  # to stderr, as argparse normally does
            emit.ended_ok()
        except ArgumentParsingError as err:
            print(err, file=sys.stderr)  # to stderr, as argparse normally does
            emit.ended_ok()
        except KeyboardInterrupt as err:
            self._emit_error(CraftError("Interrupted."), cause=err)
            retcode = 128 + signal.SIGINT
        except CraftError as err:
            self._emit_error(err)
        except Exception as err:  # noqa: BLE001 pylint: disable=broad-except
            self._emit_error(CraftError(f"{self.name} internal error: {err!r}"))
            if os.getenv("CRAFT_DEBUG") == "1":
                raise
        else:
            emit.ended_ok()

        return retcode

    def _emit_error(
        self, error: CraftError, *, cause: Optional[BaseException] = None
    ) -> None:
        """Emit the error in a centralized way so we can alter it consistently."""
        # set the cause, if any
        if cause is not None:
            error.__cause__ = cause

        # Do not report the internal logpath if running inside instance
        if self._manager.is_managed:
            error.logpath_report = False

        emit.error(error)
