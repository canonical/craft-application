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

import importlib
import os
import pathlib
import signal
import subprocess
import sys
from dataclasses import dataclass, field
from functools import cached_property
from importlib import metadata
from typing import TYPE_CHECKING, Any, Iterable, cast, final

import craft_cli
import craft_parts
import craft_providers
from xdg.BaseDirectory import save_cache_path  # type: ignore[import]

from craft_application import commands, models, secrets, util
from craft_application.models import BuildInfo

if TYPE_CHECKING:
    from craft_application.services import service_factory

GLOBAL_VERSION = craft_cli.GlobalArgument(
    "version", "flag", "-V", "--version", "Show the application version and exit"
)

DEFAULT_CLI_LOGGERS = frozenset(
    {"craft_archives", "craft_parts", "craft_providers", "craft_store"}
)


@dataclass(frozen=True)
class AppFeatures:
    """Specific features that can be enabled/disabled per-application."""

    build_secrets: bool = False
    """Support for build-time secrets."""


@final
@dataclass(frozen=True)
class AppMetadata:
    """Metadata about a *craft application."""

    name: str
    summary: str | None = None
    version: str = field(init=False)
    source_ignore_patterns: list[str] = field(default_factory=lambda: [])
    managed_instance_project_path = pathlib.PurePosixPath("/root/project")
    features: AppFeatures = AppFeatures()

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
    :param extra_loggers: Logger names to integrate with craft-cli beyond the defaults.

    """

    def __init__(
        self,
        app: AppMetadata,
        services: service_factory.ServiceFactory,
        *,
        extra_loggers: Iterable[str] = (),
    ) -> None:
        self.app = app
        self.services = services
        self._command_groups: list[craft_cli.CommandGroup] = []
        self._global_arguments: list[craft_cli.GlobalArgument] = [GLOBAL_VERSION]
        self._cli_loggers = DEFAULT_CLI_LOGGERS | set(extra_loggers)

        # When build_secrets are enabled, this contains the secret info to pass to
        # managed instances.
        self._secrets: secrets.BuildSecrets | None = None
        # Cached project object, allows only the first time we load the project
        # to specify things like the project directory.
        # This is set as a private attribute in order to discourage real application
        # implementations from accessing it directly. They should always use
        # ``get_project`` to access the project.
        self.__project: models.Project | None = None

        if self.is_managed():
            self._work_dir = pathlib.Path("/root")
        else:
            self._work_dir = pathlib.Path.cwd()

    @property
    def app_config(self) -> dict[str, Any]:
        """Get the configuration passed to dispatcher.load_command().

        This can generally be left as-is. It's strongly recommended that if you are
        overriding it, you begin with ``config = super().app_config`` and update the
        dictionary from there.
        """
        return {
            "app": self.app,
            "services": self.services,
        }

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
        if self.is_managed():
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

    def _resolve_project_path(self, project_dir: pathlib.Path | None) -> pathlib.Path:
        """Find the project file for the current project.

        The default implementation simply looks for the project file in the project
        directory. Applications may wish to override this if the project file could be
         in multiple places within the project directory.
        """
        if project_dir is None:
            project_dir = pathlib.Path.cwd()
        return (project_dir / f"{self.app.name}.yaml").resolve(strict=True)

    def get_project(self, project_dir: pathlib.Path | None = None) -> models.Project:
        """Get the project model.

        This only resolves and renders the project the first time it gets run.
        After that, it merely uses a cached project model.

        :param project_dir: the base directory to traverse for finding the project file.
        :returns: A transformed, loaded project model.
        """
        if self.__project is not None:
            return self.__project

        project_path = self._resolve_project_path(project_dir)
        craft_cli.emit.debug(f"Loading project file '{project_path!s}'")

        with project_path.open() as file:
            yaml_data = util.safe_yaml_load(file)

        yaml_data = self._transform_project_yaml(yaml_data)

        self.__project = self.app.ProjectClass.from_yaml_data(yaml_data, project_path)
        return self.__project

    @cached_property
    def project(self) -> models.Project:
        """Get this application's Project metadata."""
        return self.get_project()

    def is_managed(self) -> bool:
        """Shortcut to tell whether we're running in managed mode."""
        return self.services.ProviderClass.is_managed()

    def run_managed(self, platform: str | None, build_for: str | None) -> None:
        """Run the application in a managed instance."""
        extra_args: dict[str, Any] = {}

        build_plan = self.get_project().get_build_plan()
        build_plan = _filter_plan(build_plan, platform, build_for)

        for build_info in build_plan:
            env = {"CRAFT_PLATFORM": build_info.platform}

            if self.app.features.build_secrets:
                # If using build secrets, put them in the environment of the managed
                # instance.
                secret_values = cast(secrets.BuildSecrets, self._secrets)
                env.update(secret_values.environment)

            extra_args["env"] = env

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

    def _get_dispatcher(self) -> craft_cli.Dispatcher:
        """Configure this application. Should be called by the run method.

        Side-effect: This method may exit the process.

        :returns: A ready-to-run Dispatcher object
        """
        # Set the logging level to DEBUG for all craft-libraries. This is OK even if
        # the specific application doesn't use a specific library, the call does not
        # import the package.
        util.setup_loggers(*self._cli_loggers)

        craft_cli.emit.init(
            mode=craft_cli.EmitterMode.BRIEF,
            appname=self.app.name,
            greeting=f"Starting {self.app.name}",
            log_filepath=self.log_path,
            streaming_brief=True,
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

    def run(self) -> int:  # noqa: PLR0912 (too many branches due to error handling)
        """Bootstrap and run the application."""
        dispatcher = self._get_dispatcher()
        craft_cli.emit.trace("Preparing application...")

        return_code = 1  # General error
        try:
            command = cast(
                commands.AppCommand,
                dispatcher.load_command(self.app_config),
            )
            platform = getattr(dispatcher.parsed_args(), "platform", None)
            build_for = getattr(dispatcher.parsed_args(), "build_for", None)
            self._configure_services(platform, build_for)

            if not command.run_managed(dispatcher.parsed_args()):
                # command runs in the outer instance
                craft_cli.emit.debug(f"Running {self.app.name} {command.name} on host")
                if command.always_load_project:
                    self.services.project = self.get_project()
                return_code = dispatcher.run() or 0
            elif not self.is_managed():
                # command runs in inner instance, but this is the outer instance
                self.services.project = self.get_project()
                self.run_managed(platform, build_for)
                return_code = 0
            else:
                # command runs in inner instance
                self.services.project = self.get_project()
                return_code = dispatcher.run() or 0
        except craft_cli.ArgumentParsingError as err:
            print(err, file=sys.stderr)  # to stderr, as argparse normally does
            craft_cli.emit.ended_ok()
            return_code = 64  # Command line usage error from sysexits.h
        except KeyboardInterrupt as err:
            self._emit_error(craft_cli.CraftError("Interrupted."), cause=err)
            return_code = 128 + signal.SIGINT
        except craft_cli.CraftError as err:
            self._emit_error(err)
        except craft_parts.PartsError as err:
            self._emit_error(
                craft_cli.CraftError(
                    err.brief, details=err.details, resolution=err.resolution
                ),
                cause=err,
            )
            return_code = 1
        except craft_providers.ProviderError as err:
            self._emit_error(
                craft_cli.CraftError(
                    err.brief, details=err.details, resolution=err.resolution
                ),
                cause=err,
            )
            return_code = 1
        except Exception as err:  # noqa: BLE001 pylint: disable=broad-except
            self._emit_error(
                craft_cli.CraftError(f"{self.app.name} internal error: {err!r}"),
                cause=err,
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
        if self.is_managed():
            error.logpath_report = False

        craft_cli.emit.error(error)

    def _transform_project_yaml(self, yaml_data: dict[str, Any]) -> dict[str, Any]:
        """Update the project's yaml data with runtime properties.

        Performs task such as environment expansion. Note that this transforms
        ``yaml_data`` in-place.
        """
        # Perform variable expansion.
        self._expand_environment(yaml_data)

        # Handle build secrets.
        if self.app.features.build_secrets:
            self._render_secrets(yaml_data)

        # Perform extra, application-specific transformations.
        return self._extra_yaml_transform(yaml_data)

    def _expand_environment(self, yaml_data: dict[str, Any]) -> None:
        """Perform expansion of project environment variables."""
        project_vars = self._project_vars(yaml_data)

        info = craft_parts.ProjectInfo(
            application_name=self.app.name,  # not used in environment expansion
            cache_dir=pathlib.Path(),  # not used in environment expansion
            project_name=yaml_data.get("name", ""),
            project_dirs=craft_parts.ProjectDirs(work_dir=self._work_dir),
            project_vars=project_vars,
        )

        self._set_global_environment(info)

        craft_parts.expand_environment(yaml_data, info=info)

    def _project_vars(self, yaml_data: dict[str, Any]) -> dict[str, str]:
        """Return a dict with project-specific variables, for a craft_part.ProjectInfo."""
        return {"version": cast(str, yaml_data["version"])}

    def _set_global_environment(self, info: craft_parts.ProjectInfo) -> None:
        """Populate the ProjectInfo's global environment."""
        info.global_environment.update(
            {
                "CRAFT_PROJECT_VERSION": info.get_project_var("version", raw_read=True),
            }
        )

    def _render_secrets(self, yaml_data: dict[str, Any]) -> None:
        """Render build-secrets, in-place."""
        secret_values = secrets.render_secrets(
            yaml_data, managed_mode=self.is_managed()
        )

        num_secrets = len(secret_values.secret_strings)
        craft_cli.emit.debug(f"Project has {num_secrets} build-secret(s).")

        craft_cli.emit.set_secrets(list(secret_values.secret_strings))

        self._secrets = secret_values

    def _extra_yaml_transform(self, yaml_data: dict[str, Any]) -> dict[str, Any]:
        """Perform additional transformations on a project's yaml data.

        Note: subclasses should return a new dict and keep the parameter unmodified.
        """
        return yaml_data


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
