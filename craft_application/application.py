# This file is part of craft_application.
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
"""Main application classes for a craft-application."""
from __future__ import annotations

import functools
import os
import pathlib
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from importlib import metadata
from typing import TYPE_CHECKING, Any, cast, final

import craft_cli
import craft_providers
from xdg.BaseDirectory import save_cache_path  # type: ignore[import]

from craft_application import commands, models

if TYPE_CHECKING:
    from craft_application.services import service_factory

GLOBAL_VERSION = craft_cli.GlobalArgument(
    "version", "flag", "-V", "--version", "Show the application version and exit"
)


@final
@dataclass(frozen=True)
class AppMetadata:
    """Metadata about a *craft application."""

    name: str
    summary: str | None = None
    version: str = field(init=False)
    source_ignore_patterns: list[str] = field(default_factory=lambda: [])
    managed_instance_project_path = pathlib.PurePosixPath("/root/project")

    ProjectClass: type[models.Project] = models.Project

    def __post_init__(self) -> None:
        setter = super().__setattr__
        setter("version", metadata.version(self.name))
        if self.summary is None:
            md = metadata.metadata(self.name)
            setter("summary", md["summary"])


class Application:
    """Craft Application Builder.

    :ivar app: Metadata about this application
    :ivar services: A ServiceFactory for this application
    """

    def __init__(
        self,
        app: AppMetadata,
        services: service_factory.ServiceFactory,
    ) -> None:
        self.app = app
        self.services = services
        self._command_groups: list[craft_cli.CommandGroup] = []
        self._global_arguments: list[craft_cli.GlobalArgument] = [GLOBAL_VERSION]
        self._work_dir = pathlib.Path.cwd()

    @property
    def command_groups(self) -> list[craft_cli.CommandGroup]:
        """Return command groups."""
        lifecycle_commands = commands.get_lifecycle_command_group()

        return [lifecycle_commands, *self._command_groups]

    @property
    def log_path(self) -> pathlib.Path | None:
        """Get the path to this process's log file, if any."""
        if self.services.ProviderClass.is_managed():
            return self._managed_log_path
        return None

    @property
    def _managed_log_path(self) -> pathlib.Path:
        """Get the location of the managed instance's log file."""
        return pathlib.Path(
            f"/tmp/{self.app.name}.log"  # noqa: S108 - only applies inside managed instance.
        )

    def add_global_argument(self, argument: craft_cli.GlobalArgument) -> None:
        """Add a global argument to the Application."""
        self._global_arguments.append(argument)

    def add_command_group(
        self, name: str, commands: list[type[craft_cli.BaseCommand]]
    ) -> None:
        """Add a CommandGroup to the Application."""
        self._command_groups.append(craft_cli.CommandGroup(name, commands))

    @property
    def cache_dir(self) -> str:
        """Get the directory for caching any data."""
        # Mypy doesn't know what type save_cache_path returns, but pyright figures
        # it out correctly. We can remove this ignore comment once the typeshed has
        # xdg types: https://github.com/python/typeshed/pull/10163
        return save_cache_path(self.app.name)  # type: ignore[no-any-return]

    def _configure_services(self) -> None:
        """Configure additional keyword arguments for any service classes.

        Any child classes that override this must either call this directly or must
        provide a valid ``project`` to ``self.services``.
        """
        self.services.project = self.project
        self.services.set_kwargs(
            "lifecycle",
            cache_dir=self.cache_dir,
            work_dir=self._work_dir,
            base=self.project.effective_base,
        )

    @functools.cached_property
    def project(self) -> models.Project:
        """Get this application's Project metadata."""
        project_file = (self._work_dir / f"{self.app.name}.yaml").resolve()
        return self.app.ProjectClass.from_yaml_file(project_file)

    def run_managed(self) -> None:
        """Run the application in a managed instance."""
        craft_cli.emit.debug(f"Running {self.app.name} in a managed instance...")
        instance_path = pathlib.PosixPath("/root/project")
        with self.services.provider.instance(
            self.project.effective_base, work_dir=self._work_dir
        ) as instance:
            try:
                # Pyright doesn't fully understand craft_providers's CompletedProcess.
                instance.execute_run(  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
                    [self.app.name, *sys.argv[1:]], cwd=instance_path, check=True
                )
            except subprocess.CalledProcessError as exc:
                raise craft_providers.ProviderError(
                    f"Failed to execute {self.app.name} in instance."
                ) from exc

    def configure(self, global_args: dict[str, Any]) -> None:
        """Configure the application using any global arguments."""

    def _get_dispatcher(self) -> craft_cli.Dispatcher:
        """Configure this application. Should be called by the run method.

        Side-effect: This method may exit the process.

        :returns: A ready-to-run Dispatcher object
        """
        craft_cli.emit.init(
            mode=craft_cli.EmitterMode.BRIEF,
            appname=self.app.name,
            greeting=f"Starting {self.app.name}",
            log_filepath=self.log_path,
        )

        dispatcher = craft_cli.Dispatcher(
            self.app.name,
            self.command_groups,
            summary=str(self.app.summary),
            extra_global_args=self._global_arguments,
        )

        try:
            craft_cli.emit.trace("pre-parsing arguments...")
            # Workaround for the fact that craft_cli requires a command.
            # https://github.com/canonical/craft-cli/issues/141
            if "--version" in sys.argv or "-V" in sys.argv:
                try:
                    global_args = dispatcher.pre_parse_args(["pull", *sys.argv[1:]])
                except craft_cli.ArgumentParsingError:
                    global_args = dispatcher.pre_parse_args(sys.argv[1:])
            else:
                global_args = dispatcher.pre_parse_args(sys.argv[1:])

            if global_args.get("version"):
                craft_cli.emit.ended_ok()
                print(f"{self.app.name} {self.app.version}")
                sys.exit(0)
        except craft_cli.ProvideHelpException as err:
            print(err, file=sys.stderr)  # to stderr, as argparse normally does
            craft_cli.emit.ended_ok()
            sys.exit(0)
        except craft_cli.ArgumentParsingError as err:
            print(err, file=sys.stderr)  # to stderr, as argparse normally does
            craft_cli.emit.ended_ok()
            sys.exit(64)  # Command line usage error from sysexits.h
        except KeyboardInterrupt as err:
            self._emit_error(craft_cli.CraftError("Interrupted."), cause=err)
            sys.exit(128 + signal.SIGINT)
        except Exception as err:  # noqa: BLE001
            self._emit_error(
                craft_cli.CraftError(
                    f"Internal error while loading {self.app.name}: {err!r}"
                )
            )
            if os.getenv("CRAFT_DEBUG") == "1":
                raise
            sys.exit(70)  # EX_SOFTWARE from sysexits.h

        craft_cli.emit.trace("Preparing application...")
        self.configure(global_args)

        return dispatcher

    def run(self) -> int:
        """Bootstrap and run the application."""
        dispatcher = self._get_dispatcher()
        self._configure_services()
        craft_cli.emit.trace("Preparing application...")

        return_code = 1  # General error
        try:
            command = cast(
                commands.AppCommand,
                dispatcher.load_command(
                    {
                        "app": self.app,
                        "services": self.services,
                    }
                ),
            )
            if not command.run_managed:
                craft_cli.emit.debug(f"Running {self.app.name} {command.name} on host")
                return_code = dispatcher.run() or 0
            elif not self.services.ProviderClass.is_managed():
                self.run_managed()
                return_code = 0
            else:
                return_code = dispatcher.run() or 0
        except KeyboardInterrupt as err:
            self._emit_error(craft_cli.CraftError("Interrupted."), cause=err)
            return_code = 128 + signal.SIGINT
        except craft_cli.CraftError as err:
            self._emit_error(err)
        except Exception as err:  # noqa: BLE001 pylint: disable=broad-except
            self._emit_error(
                craft_cli.CraftError(f"{self.app.name} internal error: {err!r}")
            )
            if os.getenv("CRAFT_DEBUG") == "1":
                raise
            return_code = 70  # EX_SOFTWARE from sysexits.h
        else:
            craft_cli.emit.ended_ok()

        return return_code

    def _emit_error(
        self, error: craft_cli.CraftError, *, cause: BaseException | None = None
    ) -> None:
        """Emit the error in a centralized way so we can alter it consistently."""
        # set the cause, if any
        if cause is not None:
            error.__cause__ = cause

        # Do not report the internal logpath if running inside an instance
        if self.services.ProviderClass.is_managed():
            error.logpath_report = False

        craft_cli.emit.error(error)
