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

import argparse
import functools
import importlib
import os
import pathlib
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from importlib import metadata
from typing import TYPE_CHECKING, Any, cast, final

import craft_cli
import craft_parts
import craft_providers
from xdg.BaseDirectory import save_cache_path  # type: ignore[import]

from craft_application import commands, models, util
from craft_application.models import BuildInfo

if TYPE_CHECKING:
    from craft_application.services import service_factory

GLOBAL_VERSION = craft_cli.GlobalArgument(
    "version", "flag", "-V", "--version", "Show the application version and exit"
)


class _Dispatcher(craft_cli.Dispatcher):
    """Application command dispatcher."""

    @property
    def parsed_args(self) -> argparse.Namespace:
        """The map of parsed command-line arguments."""
        return self._parsed_command_args or argparse.Namespace()


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

        # Try to determine the app version.
        try:
            # First, via the __version__ attribute on the app's main package.
            version = importlib.import_module(self.name).__version__
        except (AttributeError, ModuleNotFoundError):
            try:
                # If that fails, try via the installed metadata.
                version = metadata.version(self.name)
            except metadata.PackageNotFoundError:
                # If that fails too, default to "dev".
                version = "dev"

        setter("version", version)
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

        if self.services.ProviderClass.is_managed():
            self._work_dir = pathlib.Path("/root")
        else:
            self._work_dir = pathlib.Path.cwd()

    @property
    def command_groups(self) -> list[craft_cli.CommandGroup]:
        """Return command groups."""
        lifecycle_commands = commands.get_lifecycle_command_group()
        other_commands = commands.get_other_command_group()

        merged: dict[str, list[type[craft_cli.BaseCommand]]] = {}
        all_groups = [lifecycle_commands, other_commands, *self._command_groups]

        # Merge the default command groups with those provided by the application,
        # so that we don't get multiple groups with the same name.
        for group in all_groups:
            merged.setdefault(group.name, []).extend(group.commands)

        return [
            craft_cli.CommandGroup(name, commands_)
            for name, commands_ in merged.items()
        ]

    @property
    def log_path(self) -> pathlib.Path | None:
        """Get the path to this process's log file, if any."""
        if self.services.ProviderClass.is_managed():
            return util.get_managed_logpath(self.app)
        return None

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

    def _configure_services(
        self,
        platform: str | None,  # noqa: ARG002 (Unused method argument)
        build_for: str | None,
    ) -> None:
        """Configure additional keyword arguments for any service classes.

        Any child classes that override this must either call this directly or must
        provide a valid ``project`` to ``self.services``.
        """
        self.services.set_kwargs(
            "lifecycle",
            cache_dir=self.cache_dir,
            work_dir=self._work_dir,
            build_for=build_for,
        )
        self.services.set_kwargs(
            "provider",
            work_dir=self._work_dir,
        )

    @functools.cached_property
    def project(self) -> models.Project:
        """Get this application's Project metadata."""
        # Current working directory contains the project file
        project_file = pathlib.Path(f"{self.app.name}.yaml").resolve()
        craft_cli.emit.debug(f"Loading project file '{project_file!s}'")
        return self.app.ProjectClass.from_yaml_file(project_file)

    def run_managed(self, platform: str | None, build_for: str | None) -> None:
        """Run the application in a managed instance."""
        extra_args: dict[str, Any] = {}

        build_plan = self.project.get_build_plan()
        build_plan = _filter_plan(build_plan, platform, build_for)

        for build_info in build_plan:
            extra_args["env"] = {"CRAFT_PLATFORM": build_info.platform}

            craft_cli.emit.debug(
                f"Running {self.app.name}:{build_info.platform} in {build_info.build_for} instance..."
            )
            instance_path = pathlib.PosixPath("/root/project")

            with self.services.provider.instance(
                build_info, work_dir=self._work_dir
            ) as instance:
                try:
                    # Pyright doesn't fully understand craft_providers's CompletedProcess.
                    instance.execute_run(  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
                        [self.app.name, *sys.argv[1:]],
                        cwd=instance_path,
                        check=True,
                        **extra_args,
                    )
                except subprocess.CalledProcessError as exc:
                    raise craft_providers.ProviderError(
                        f"Failed to execute {self.app.name} in instance."
                    ) from exc

    def configure(self, global_args: dict[str, Any]) -> None:
        """Configure the application using any global arguments."""

    def _get_dispatcher(self) -> _Dispatcher:
        """Configure this application. Should be called by the run method.

        Side-effect: This method may exit the process.

        :returns: A ready-to-run Dispatcher object
        """
        craft_cli.emit.init(
            mode=craft_cli.EmitterMode.BRIEF,
            appname=self.app.name,
            greeting=f"Starting {self.app.name}",
            log_filepath=self.log_path,
            streaming_brief=True,
        )

        dispatcher = _Dispatcher(
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
            platform = getattr(dispatcher.parsed_args, "platform", None)
            build_for = getattr(dispatcher.parsed_args, "build_for", None)
            self._configure_services(platform, build_for)

            if not command.run_managed(dispatcher.parsed_args):
                # command runs in the outer instance
                craft_cli.emit.debug(f"Running {self.app.name} {command.name} on host")
                if command.always_load_project:
                    self.services.project = self.project
                return_code = dispatcher.run() or 0
            elif not self.services.ProviderClass.is_managed():
                # command runs in inner instance, but this is the outer instance
                self.services.project = self.project
                self.run_managed(platform, build_for)
                return_code = 0
            else:
                # command runs in inner instance
                self.services.project = self.project
                return_code = dispatcher.run() or 0
        except KeyboardInterrupt as err:
            self._emit_error(craft_cli.CraftError("Interrupted."), cause=err)
            return_code = 128 + signal.SIGINT
        except craft_cli.CraftError as err:
            self._emit_error(err)
        except craft_parts.PartsError as err:
            self._emit_error(
                craft_cli.CraftError(
                    err.brief, details=err.details, resolution=err.resolution
                )
            )
            return_code = 1
        except craft_providers.ProviderError as err:
            self._emit_error(
                craft_cli.CraftError(
                    err.brief, details=err.details, resolution=err.resolution
                )
            )
            return_code = 1
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


def _filter_plan(
    build_plan: list[BuildInfo], platform: str | None, build_for: str | None
) -> list[BuildInfo]:
    """Filter out builds not matching build-on and build-for."""
    host_arch = util.get_host_architecture()

    plan: list[BuildInfo] = []
    for build_info in build_plan:
        platform_matches = not platform or build_info.platform == platform
        build_on_matches = build_info.build_on == host_arch
        build_for_matches = not build_for or build_info.build_for == build_for

        if platform_matches and build_on_matches and build_for_matches:
            plan.append(build_info)

    return plan
