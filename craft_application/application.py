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
"""Main application classes for a craft-application."""

from __future__ import annotations

import importlib
import os
import pathlib
import signal
import subprocess
import sys
import traceback
import warnings
from dataclasses import dataclass, field
from functools import cached_property
from importlib import metadata
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast, final

import annotated_types
import craft_cli
import craft_providers
from platformdirs import user_cache_path

from craft_application import _config, commands, errors, models, util
from craft_application.errors import PathInvalidError
from craft_application.util.logging import handle_runtime_error

if TYPE_CHECKING:
    import argparse
    from collections.abc import Iterable, Sequence

    from craft_parts.infos import ProjectInfo
    from craft_parts.plugins.plugins import PluginType

    from craft_application.services import service_factory

GLOBAL_VERSION = craft_cli.GlobalArgument(
    "version", "flag", "-V", "--version", "Show the application version and exit"
)

DEFAULT_CLI_LOGGERS = frozenset(
    {
        "craft_archives",
        "craft_parts",
        "craft_providers",
        "craft_store",
        "craft_application",
        "httpx",  # Used by craft-store
    }
)


@final
@dataclass(frozen=True)
class AppMetadata:
    """Metadata about a craft application."""

    name: str
    """The name of the application."""
    summary: str | None = None
    """A short summary of the application."""
    version: str = field(init=False)
    docs_url: str | None = None
    """The root URL for the app's documentation."""
    artifact_type: Annotated[
        str,
        annotated_types.IsAscii,
        annotated_types.LowerCase,
    ] = "artifact"
    """The name to refer to the output artifact for this app.

    This gets used in messages and should be an all lower-case single-word value, like
    ``snap`` or ``rock``. Defaults to ``artifact``.
    """
    source_ignore_patterns: list[str] = field(default_factory=list[str])
    managed_instance_project_path = pathlib.PurePosixPath("/root/project")
    project_variables: list[str] = field(default_factory=lambda: ["version"])
    mandatory_adoptable_fields: list[str] = field(default_factory=lambda: ["version"])
    ConfigModel: type[_config.ConfigModel] = _config.ConfigModel

    ProjectClass: type[models.Project] = models.Project
    """The project model to use for this app.

    Most applications will need to override this, but a very basic application could use
    the default model without modification.
    """
    supports_multi_base: bool = False
    always_repack: bool = (
        True  # Gating for https://github.com/canonical/craft-application/pull/810
    )
    check_supported_base: bool = False
    """Whether this application allows building on unsupported bases.

    When True, the app can build on a base even if it is end-of-life. Relevant apt
    repositories will be migrated to ``old-releases.ubuntu.com``. Currently only
    supports EOL Ubuntu releases.

    When False, the repositories are not migrated and base support is not checked.
    """

    enable_for_grammar: bool = False
    """Whether this application supports the 'for' variant of advanced grammar."""

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

    @property
    def versioned_docs_url(self) -> str | None:
        """The ``docs_url`` with the proper app version."""
        if self.docs_url is None:
            return None

        return util.render_doc_url(self.docs_url, self.version)


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
        self._partitions: list[str] | None = None
        # Cached project object, allows only the first time we load the project
        # to specify things like the project directory.
        # This is set as a private attribute in order to discourage real application
        # implementations from accessing it directly. They should always use
        # ``get_project`` to access the project.
        self.__project: models.Project | None = None
        # Set a globally usable project directory for the application.
        # This may be overridden by specific application implementations.
        self.project_dir = pathlib.Path.cwd()

        if self.is_managed():
            self._work_dir = pathlib.Path("/root")
        else:
            self._work_dir = pathlib.Path.cwd()

        # Whether the command execution should use the fetch-service
        self._enable_fetch_service = False
        # The kind of sessions that the fetch-service service should create
        self._fetch_service_policy: Literal["strict", "permissive"] = "strict"

    @final
    def _load_plugins(self) -> None:
        """Load application plugins."""
        # https://packaging.python.org/en/latest/specifications/entry-points/#data-model
        for plugin_entry_point in metadata.entry_points(
            group="craft_application_plugins.application"
        ):
            craft_cli.emit.debug(f"Loading app plugin {plugin_entry_point.name}")
            try:
                app_plugin_module = plugin_entry_point.load()
                app_plugin_module.configure(self)
            except Exception:  # noqa: BLE001
                craft_cli.emit.progress(
                    f"Failed to load plugin {plugin_entry_point.name}",
                    permanent=True,
                )
                craft_cli.emit.debug(traceback.format_exc())

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
        """Return command groups.

        Merges command groups provided by the application with craft-application's
        default commands.

        If the application and craft-application provide a command with the same name
        in the same group, the application's command is used.

        Note that a command with the same name cannot exist in multiple groups.
        """
        lifeycle_default_commands = commands.get_lifecycle_command_group()
        other_default_commands = commands.get_other_command_group()

        merged = {group.name: group for group in self._command_groups}

        merged[lifeycle_default_commands.name] = self._merge_defaults(
            app_commands=merged.get(lifeycle_default_commands.name),
            default_commands=lifeycle_default_commands,
        )
        merged[other_default_commands.name] = self._merge_defaults(
            app_commands=merged.get(other_default_commands.name),
            default_commands=other_default_commands,
        )

        return list(merged.values())

    def _merge_defaults(
        self,
        *,
        app_commands: craft_cli.CommandGroup | None,
        default_commands: craft_cli.CommandGroup,
    ) -> craft_cli.CommandGroup:
        """Merge default commands with application commands for a particular group.

        Default commands are only used if the application does not have a command
        with the same name.

        The order of the merged commands follow the order of the default commands.
        Extra application commands are appended to the end of the command list.

        :param app_commands: The application's commands.
        :param default_commands: Craft Application's default commands.

        :returns: A list of app commands and default commands.
        """
        if not app_commands:
            return default_commands

        craft_cli.emit.debug(f"Merging commands for group {default_commands.name!r}:")

        # for lookup of commands by name
        app_commands_dict = {command.name: command for command in app_commands.commands}

        merged_commands: list[type[craft_cli.BaseCommand]] = []
        processed_command_names: set[str] = set()

        for default_command in default_commands.commands:
            # prefer the application command if it exists
            command_name = default_command.name
            if command_name in app_commands_dict:
                craft_cli.emit.debug(
                    f"  - using application command for {command_name!r}."
                )
                merged_commands.append(app_commands_dict[command_name])
                processed_command_names.add(command_name)
            # otherwise use the default
            else:
                merged_commands.append(default_command)

        # append remaining commands from the application
        merged_commands.extend(
            app_command
            for app_command in app_commands.commands
            if app_command.name not in processed_command_names
        )

        return craft_cli.CommandGroup(
            name=default_commands.name,
            commands=merged_commands,
            ordered=default_commands.ordered,
        )

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
        self,
        name: str,
        commands: Sequence[type[craft_cli.BaseCommand]],
        *,
        ordered: bool = False,
    ) -> None:
        """Add a CommandGroup to the Application."""
        self._command_groups.append(craft_cli.CommandGroup(name, commands, ordered))

    @cached_property
    def cache_dir(self) -> pathlib.Path:
        """Get the directory for caching any data."""
        try:
            return user_cache_path(self.app.name, ensure_exists=True)
        except FileExistsError as err:
            raise PathInvalidError(
                f"The cache path is not a directory: {err.strerror}"
            ) from err
        except OSError as err:
            raise PathInvalidError(
                f"Unable to create/access cache directory: {err.strerror}"
            ) from err

    def _configure_early_services(self) -> None:
        """Configure early-starting services.

        This should only contain configuration for services that are needed during
        application startup. All other configuration belongs in ``_configure_services``
        """
        self.services.update_kwargs(
            "project",
            project_dir=self.project_dir,
        )

    def _configure_services(self, provider_name: str | None) -> None:
        """Configure additional keyword arguments for any service classes.

        Any child classes that override this must either call this directly or must
        provide a valid ``project`` to ``self.services``.
        """
        self.services.update_kwargs(
            "lifecycle",
            cache_dir=self.cache_dir,
            work_dir=self._work_dir,
        )
        self.services.update_kwargs(
            "provider",
            work_dir=self._work_dir,
            provider_name=provider_name,
        )

    def get_project(
        self,
        *,
        platform: str | None = None,
        build_for: str | None = None,
    ) -> models.Project:
        """Get the project model.

        This only resolves and renders the project the first time it gets run.
        After that, it merely uses a cached project model.

        :param platform: the platform name listed in the build plan.
        :param build_for: the architecture to build this project for.
        :returns: A transformed, loaded project model.
        """
        warnings.warn(
            DeprecationWarning(
                "Do not get the project directly from the Application. "
                "Get it from the project service."
            ),
            stacklevel=2,
        )
        project_service = self.services.get("project")
        if not project_service.is_configured:
            project_service.configure(platform=platform, build_for=build_for)
        return project_service.get()

    @cached_property
    def project(self) -> models.Project:
        """Get this application's Project metadata."""
        return self.get_project()

    def is_managed(self) -> bool:
        """Shortcut to tell whether we're running in managed mode."""
        return self.services.get_class("provider").is_managed()

    def run_managed(self, platform: str | None, build_for: str | None) -> None:
        """Run the application in a managed instance."""
        build_planner = self.services.get("build_plan")
        if platform:
            build_planner.set_platforms(platform)
        if build_for:
            build_planner.set_build_fors(build_for)
        plan = build_planner.plan()

        if not plan:
            raise errors.EmptyBuildPlanError

        if self._enable_fetch_service:
            self.services.get("fetch").set_policy(self._fetch_service_policy)

        extra_args: dict[str, Any] = {}
        for build_info in plan:
            env = {
                "CRAFT_PLATFORM": build_info.platform,
                "CRAFT_VERBOSITY_LEVEL": craft_cli.emit.get_mode().name,
            }

            extra_args["env"] = env

            craft_cli.emit.debug(
                f"Running {self.app.name}:{build_info.platform} in {build_info.build_for} instance..."
            )
            instance_path = pathlib.PosixPath("/root/project")
            active_fetch_service = self.services.get("fetch").is_active(
                enable_command_line=self._enable_fetch_service
            )

            with self.services.provider.instance(
                build_info,
                work_dir=self._work_dir,
                clean_existing=self._enable_fetch_service,
                use_base_instance=not active_fetch_service,
            ) as instance:
                if self._enable_fetch_service:
                    fetch_env = self.services.fetch.create_session(instance)
                    env.update(fetch_env)

                session_env = self.services.get("proxy").configure_instance(instance)
                env.update(session_env)

                cmd = [self.app.name, *sys.argv[1:]]
                craft_cli.emit.debug(
                    f"Executing {cmd} in instance location {instance_path} with {extra_args}."
                )
                try:
                    with craft_cli.emit.pause():
                        # Pyright doesn't fully understand craft_providers's CompletedProcess.
                        instance.execute_run(  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
                            cmd,
                            cwd=instance_path,
                            check=True,
                            **extra_args,
                        )
                except subprocess.CalledProcessError as exc:
                    raise craft_providers.ProviderError(
                        f"Failed to execute {self.app.name} in instance."
                    ) from exc
                finally:
                    if self._enable_fetch_service:
                        self.services.fetch.teardown_session()

        if self._enable_fetch_service:
            self.services.fetch.shutdown(force=True)

    def configure(self, global_args: dict[str, Any]) -> None:
        """Configure the application using any global arguments."""

    def _get_dispatcher(self) -> craft_cli.Dispatcher:
        """Configure this application.

        Should be called by the _run_inner method.
        Side-effect: This method may exit the process.

        :returns: A ready-to-run Dispatcher object
        """
        dispatcher = self._create_dispatcher()

        try:
            craft_cli.emit.trace("pre-parsing arguments...")
            app_config = self.app_config
            # Workaround for the fact that craft_cli requires a command.
            # https://github.com/canonical/craft-cli/issues/141
            if "--version" in sys.argv or "-V" in sys.argv:
                try:
                    global_args = dispatcher.pre_parse_args(
                        ["pull", *sys.argv[1:]], app_config
                    )
                except craft_cli.ArgumentParsingError:
                    global_args = dispatcher.pre_parse_args(sys.argv[1:], app_config)
            else:
                global_args = dispatcher.pre_parse_args(sys.argv[1:], app_config)

            if global_args.get("version"):
                craft_cli.emit.message(f"{self.app.name} {self.app.version}")
                craft_cli.emit.ended_ok()
                sys.exit(0)
        except craft_cli.ProvideHelpException as err:
            print(err, file=sys.stderr)  # to stderr, as argparse normally does
            craft_cli.emit.ended_ok()
            sys.exit(0)
        except craft_cli.ArgumentParsingError as err:
            print(err, file=sys.stderr)  # to stderr, as argparse normally does
            craft_cli.emit.ended_ok()
            sys.exit(os.EX_USAGE)
        except KeyboardInterrupt as err:
            self._emit_error(craft_cli.CraftError("Interrupted."), cause=err)
            sys.exit(128 + signal.SIGINT)
        except Exception as err:
            self._emit_error(
                craft_cli.CraftError(
                    f"Internal error while loading {self.app.name}: {err!r}"
                )
            )
            if self.services.config.get("debug"):
                raise
            sys.exit(os.EX_SOFTWARE)

        craft_cli.emit.debug("Configuring application...")
        self.configure(global_args)

        return dispatcher

    def _create_dispatcher(self) -> craft_cli.Dispatcher:
        """Create the Dispatcher that will run the application's command.

        Subclasses can override this if they need to create a Dispatcher with
        different parameters.
        """
        return craft_cli.Dispatcher(
            self.app.name,
            self.command_groups,
            summary=str(self.app.summary),
            extra_global_args=self._global_arguments,
            docs_base_url=self.app.versioned_docs_url,
        )

    def _get_app_plugins(self) -> dict[str, PluginType]:
        """Get the plugins for this application.

        Should be overridden by applications that need to register plugins at startup.
        """
        return {}

    def register_plugins(self, plugins: dict[str, PluginType]) -> None:
        """Register plugins for this application."""
        if not plugins:
            return
        from craft_parts.plugins import register  # noqa: PLC0415

        craft_cli.emit.trace("Registering plugins...")
        craft_cli.emit.trace(f"Plugins: {', '.join(plugins.keys())}")
        register(plugins)

    def _register_default_plugins(self) -> None:
        """Register per application plugins when initializing."""
        self.register_plugins(self._get_app_plugins())

    def _pre_run(self, dispatcher: craft_cli.Dispatcher) -> None:
        """Do any final setup before running the command.

        At the time this is run, the command is loaded in the dispatcher, but
        the project has not yet been loaded.
        """
        args = dispatcher.parsed_args()

        # Some commands might have a project_dir parameter. Those commands and
        # only those commands should get a project directory, but only when
        # not managed.
        if self.is_managed():
            self.project_dir = pathlib.Path("/root/project")
        elif project_dir := getattr(args, "project_dir", None):
            self.project_dir = pathlib.Path(project_dir).expanduser().resolve()
            if self.project_dir.exists() and not self.project_dir.is_dir():
                raise errors.ProjectFileMissingError(
                    "Provided project directory is not a directory.",
                    details=f"Not a directory: {project_dir}",
                    resolution="Ensure the path entered is correct.",
                )

        fetch_service_policy: str | None = getattr(args, "fetch_service_policy", None)
        if fetch_service_policy:
            self._enable_fetch_service = True
            self._fetch_service_policy = fetch_service_policy  # type: ignore[assignment]

    def get_arg_or_config(self, parsed_args: argparse.Namespace, item: str) -> Any:  # noqa: ANN401
        """Get a configuration option that could be overridden by a command argument.

        :param parsed_args: The argparse Namespace to check.
        :param item: the name of the namespace or config item.
        :returns: the requested value.
        """
        arg_value = getattr(parsed_args, item, None)
        if arg_value is not None:
            return arg_value
        return self.services.get("config").get(item)

    def _run_inner(self) -> int:
        """Actual run implementation."""
        dispatcher = self._get_dispatcher()
        command = cast(
            commands.AppCommand,
            dispatcher.load_command(self.app_config),
        )
        parsed_args = dispatcher.parsed_args()
        platform = self.get_arg_or_config(parsed_args, "platform")
        build_for = self.get_arg_or_config(parsed_args, "build_for")

        # Some commands (e.g. remote build) can allow multiple platforms
        # or build-fors, comma-separated. In these cases, we create the
        # project using the first defined platform.
        if platform and "," in platform:
            platform = platform.split(",", maxsplit=1)[0]
        if build_for and "," in build_for:
            build_for = build_for.split(",", maxsplit=1)[0]
        craft_cli.emit.debug(f"Build plan: platform={platform}, build_for={build_for}")

        self._pre_run(dispatcher)

        if command.needs_project(parsed_args):
            project_service = self.services.get("project")
            # This branch always runs, except during testing.
            if not project_service.is_configured:
                project_service.configure(platform=platform, build_for=build_for)

        managed_mode = command.run_managed(parsed_args)
        provider_name = command.provider_name(parsed_args)
        self._configure_services(provider_name)

        return_code = 1  # General error
        if not managed_mode:
            # command runs in the outer instance
            craft_cli.emit.debug(f"Running {self.app.name} {command.name} on host")
            return_code = dispatcher.run() or os.EX_OK
        elif not self.is_managed():
            # command runs in inner instance, but this is the outer instance
            self.run_managed(platform, build_for)
            return_code = os.EX_OK
        else:
            # command runs in inner instance
            return_code = dispatcher.run() or 0

        return return_code

    def run(self) -> int:
        """Bootstrap and run the application."""
        self._setup_logging()
        self._configure_early_services()
        self._initialize_craft_parts()
        self._load_plugins()

        craft_cli.emit.debug("Preparing application...")

        debug_mode = self.services.get("config").get("debug")

        try:
            return_code = self._run_inner()
        # Other BaseException classes should be passed through, not caught.
        except (Exception, KeyboardInterrupt) as error:  # noqa: BLE001, this is not blind due to the handler code
            return_code = handle_runtime_error(
                self.app, error, print_error=self._emit_error, debug_mode=debug_mode
            )
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

    def _get_project_vars(self, yaml_data: dict[str, Any]) -> dict[str, str]:
        """Return a dict with project variables to be expanded.

        DEPRECATED: This method is deprecated and is not called by default.
        Use ``ProjectService.project_vars`` instead.
        """
        warnings.warn(
            "'Application._get_project_vars' is deprecated. "
            "Use 'ProjectService.project_vars' instead.",
            category=DeprecationWarning,
            stacklevel=1,
        )

        pvars: dict[str, str] = {}
        for var in self.app.project_variables:
            pvars[var] = str(yaml_data.get(var, ""))
        return pvars

    def _set_global_environment(self, info: ProjectInfo) -> None:
        """Populate the ProjectInfo's global environment.

        DEPRECATED: This method is deprecated and is not called by default.
        Use ``ProjectService.update_project_environment`` instead.
        """
        warnings.warn(
            "Application._set_global_environment is deprecated and not called by "
            "default. Use ProjectService.update_project_environment instead.",
            category=DeprecationWarning,
            stacklevel=1,
        )
        info.global_environment.update(
            {
                "CRAFT_PROJECT_VERSION": info.get_project_var("version", raw_read=True),
            }
        )

    def _setup_logging(self) -> None:
        """Initialize the logging system."""
        # Set the logging level to DEBUG for all craft-libraries. This is OK even if
        # the specific application doesn't use a specific library, the call does not
        # import the package.
        emitter_mode: craft_cli.EmitterMode = craft_cli.EmitterMode.BRIEF
        invalid_emitter_level = False
        util.setup_loggers(*self._cli_loggers)

        # environment variable takes precedence over the default
        emitter_verbosity_level_env = os.environ.get("CRAFT_VERBOSITY_LEVEL", None)

        if emitter_verbosity_level_env:
            try:
                emitter_mode = craft_cli.EmitterMode[
                    emitter_verbosity_level_env.strip().upper()
                ]
            except KeyError:
                invalid_emitter_level = True

        craft_cli.emit.init(
            mode=emitter_mode,
            appname=self.app.name,
            greeting=f"Starting {self.app.name}, version {self.app.version}",
            log_filepath=self.log_path,
            streaming_brief=True,
            docs_base_url=self.app.versioned_docs_url,
        )

        craft_cli.emit.debug(f"Log verbosity level set to {emitter_mode.name}")

        if invalid_emitter_level:
            craft_cli.emit.progress(
                f"Invalid verbosity level '{emitter_verbosity_level_env}', using default 'BRIEF'.\n"
                f"Valid levels are: {', '.join(emitter.name for emitter in craft_cli.EmitterMode)}",
                permanent=True,
            )

    def _enable_craft_parts_features(self) -> None:
        """Enable any specific craft-parts Feature that the application will need."""

    def _initialize_craft_parts(self) -> None:
        """Perform craft-parts-specific initialization, like features and plugins."""
        self._enable_craft_parts_features()
        self._register_default_plugins()
