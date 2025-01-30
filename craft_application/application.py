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

import argparse
import importlib
import os
import pathlib
import signal
import subprocess
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from functools import cached_property
from importlib import metadata
from typing import TYPE_CHECKING, Any, cast, final

import craft_cli
import craft_parts
import craft_providers
import craft_providers.lxd
from craft_parts.plugins.plugins import PluginType
from platformdirs import user_cache_path

from craft_application import _config, commands, errors, grammar, models, secrets, util
from craft_application.errors import InvalidUbuntuProStatusError, PathInvalidError
from craft_application.models import BuildInfo, GrammarAwareProject
from craft_application.util import ProServices, ValidatorOptions

if TYPE_CHECKING:
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
    }
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
    docs_url: str | None = None
    source_ignore_patterns: list[str] = field(default_factory=list)
    managed_instance_project_path = pathlib.PurePosixPath("/root/project")
    features: AppFeatures = AppFeatures()
    project_variables: list[str] = field(default_factory=lambda: ["version"])
    mandatory_adoptable_fields: list[str] = field(default_factory=lambda: ["version"])
    ConfigModel: type[_config.ConfigModel] = _config.ConfigModel

    ProjectClass: type[models.Project] = models.Project
    BuildPlannerClass: type[models.BuildPlanner] = models.BuildPlanner

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
        self._full_build_plan: list[models.BuildInfo] = []
        self._build_plan: list[models.BuildInfo] = []
        # When build_secrets are enabled, this contains the secret info to pass to
        # managed instances.
        self._secrets: secrets.BuildSecrets | None = None
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
        # Ubuntu ProServices instance containing relevant pro services specified by the user.
        # Storage of this instance may change in the future as we migrate Pro operations towards
        # an application service.
        self._pro_services: ProServices | None = None

        if self.is_managed():
            self._work_dir = pathlib.Path("/root")
        else:
            self._work_dir = pathlib.Path.cwd()

        # Whether the command execution should use the fetch-service
        self._enable_fetch_service = False
        # The kind of sessions that the fetch-service service should create
        self._fetch_service_policy = "strict"

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

    def _configure_services(self, provider_name: str | None) -> None:
        """Configure additional keyword arguments for any service classes.

        Any child classes that override this must either call this directly or must
        provide a valid ``project`` to ``self.services``.
        """
        self.services.update_kwargs(
            "lifecycle",
            cache_dir=self.cache_dir,
            work_dir=self._work_dir,
            build_plan=self._build_plan,
            partitions=self._partitions,
            use_host_sources=bool(self._pro_services),
        )
        self.services.update_kwargs(
            "provider",
            work_dir=self._work_dir,
            build_plan=self._build_plan,
            provider_name=provider_name,
        )
        self.services.update_kwargs(
            "fetch",
            build_plan=self._build_plan,
            session_policy=self._fetch_service_policy,
        )

    def _resolve_project_path(self, project_dir: pathlib.Path | None) -> pathlib.Path:
        """Find the project file for the current project.

        The default implementation simply looks for the project file in the project
        directory. Applications may wish to override this if the project file could be
         in multiple places within the project directory.
        """
        if project_dir is None:
            project_dir = self.project_dir

        return (project_dir / f"{self.app.name}.yaml").resolve(strict=True)

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
        if self.__project is not None:
            return self.__project

        try:
            project_path = self._resolve_project_path(self.project_dir)
        except FileNotFoundError as err:
            raise errors.ProjectFileMissingError(
                f"Project file '{self.app.name}.yaml' not found in '{self.project_dir}'.",
                details="The project file could not be found.",
                resolution="Ensure the project file exists.",
                retcode=os.EX_NOINPUT,
            ) from err
        craft_cli.emit.debug(f"Loading project file '{project_path!s}'")

        with project_path.open() as file:
            yaml_data = util.safe_yaml_load(file)

        host_arch = util.get_host_architecture()
        build_planner = self.app.BuildPlannerClass.from_yaml_data(
            yaml_data, project_path
        )
        self._full_build_plan = build_planner.get_build_plan()
        self._build_plan = filter_plan(
            self._full_build_plan, platform, build_for, host_arch
        )

        if not build_for:
            # get the build-for arch from the platform
            if platform:
                all_platforms = {b.platform: b for b in self._full_build_plan}
                if platform not in all_platforms:
                    raise errors.InvalidPlatformError(
                        platform, list(all_platforms.keys())
                    )
                build_for = all_platforms[platform].build_for
            # otherwise get the build-for arch from the build plan
            elif self._build_plan:
                build_for = self._build_plan[0].build_for

        # validate project grammar
        GrammarAwareProject.validate_grammar(yaml_data)

        build_on = host_arch

        # Setup partitions, some projects require the yaml data, most will not
        self._partitions = self._setup_partitions(yaml_data)
        yaml_data = self._transform_project_yaml(yaml_data, build_on, build_for)
        self.__project = self.app.ProjectClass.from_yaml_data(yaml_data, project_path)

        # check if mandatory adoptable fields exist if adopt-info not used
        for name in self.app.mandatory_adoptable_fields:
            if (
                not getattr(self.__project, name, None)
                and not self.__project.adopt_info
            ):
                raise errors.CraftValidationError(
                    f"Required field '{name}' is not set and 'adopt-info' not used."
                )

        return self.__project

    @cached_property
    def project(self) -> models.Project:
        """Get this application's Project metadata."""
        return self.get_project()

    def is_managed(self) -> bool:
        """Shortcut to tell whether we're running in managed mode."""
        return self.services.get_class("provider").is_managed()

    def _configure_instance_with_pro(self, instance: craft_providers.Executor) -> None:
        """Configure an instance with Ubuntu Pro. Currently we only support LXD instances."""
        # TODO: Remove craft_provider typing ignores after feature/pro-sources # noqa: FIX002
        # has been merged into main.

        # Check if the instance has pro services enabled and if they match the requested services.
        # If not, raise an Exception and bail out.
        if (
            isinstance(instance, craft_providers.lxd.LXDInstance)
            and instance.pro_services is not None  # type: ignore  # noqa: PGH003
            and instance.pro_services != self._pro_services  # type: ignore  # noqa: PGH003
        ):
            raise InvalidUbuntuProStatusError(self._pro_services, instance.pro_services)  # type: ignore  # noqa: PGH003

        # if pro services are required, ensure the pro client is
        # installed, attached and the correct services are enabled
        if self._pro_services:
            # Suggestion: create a Pro abstract class used to ensure minimum support by instances.
            # we can then check for pro support by inheritance.
            if not isinstance(instance, craft_providers.lxd.LXDInstance):
                raise errors.UbuntuProNotSupportedError(
                    "Ubuntu Pro builds are only supported with LXC backend."
                )

            craft_cli.emit.debug(
                f"Enabling Ubuntu Pro Services {self._pro_services}, {set(self._pro_services)}"
            )
            instance.install_pro_client()  # type: ignore  # noqa: PGH003
            instance.attach_pro_subscription()  # type: ignore  # noqa: PGH003
            instance.enable_pro_service(self._pro_services)  # type: ignore  # noqa: PGH003

        # Cache the current pro services, for prior checks in reentrant calls.
        if self._pro_services is not None:
            instance.pro_services = self._pro_services  # type: ignore  # noqa: PGH003

    def run_managed(self, platform: str | None, build_for: str | None) -> None:
        """Run the application in a managed instance."""
        if not self._build_plan:
            raise errors.EmptyBuildPlanError

        extra_args: dict[str, Any] = {}
        for build_info in self._build_plan:
            if platform and platform != build_info.platform:
                continue

            if build_for and build_for != build_info.build_for:
                continue

            env = {
                "CRAFT_PLATFORM": build_info.platform,
                "CRAFT_VERBOSITY_LEVEL": craft_cli.emit.get_mode().name,
            }

            if self.app.features.build_secrets:
                # If using build secrets, put them in the environment of the managed
                # instance.
                secret_values = cast(secrets.BuildSecrets, self._secrets)
                # disable logging CRAFT_SECRETS value passed to the managed instance
                craft_cli.emit.set_secrets(list(secret_values.environment.values()))

                env.update(secret_values.environment)

            extra_args["env"] = env

            craft_cli.emit.debug(
                f"Running {self.app.name}:{build_info.platform} in {build_info.build_for} instance..."
            )
            instance_path = pathlib.PosixPath("/root/project")

            with self.services.provider.instance(
                build_info,
                work_dir=self._work_dir,
                clean_existing=self._enable_fetch_service,
            ) as instance:
                if self._enable_fetch_service:
                    session_env = self.services.fetch.create_session(instance)
                    env.update(session_env)

                self._configure_instance_with_pro(instance)

                cmd = [self.app.name, *sys.argv[1:]]
                craft_cli.emit.debug(
                    f"Executing {cmd} in instance location {instance_path} with {extra_args}."
                )
                try:
                    with craft_cli.emit.pause():
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

        craft_cli.emit.trace("Registering plugins...")
        craft_cli.emit.trace(f"Plugins: {', '.join(plugins.keys())}")
        craft_parts.plugins.register(plugins)

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
            self._fetch_service_policy = fetch_service_policy

    def get_arg_or_config(self, parsed_args: argparse.Namespace, item: str) -> Any:  # noqa: ANN401
        """Get a configuration option that could be overridden by a command argument.

        :param parsed_args: The argparse Namespace to check.
        :param item: the name of the namespace or config item.
        :returns: the requested value.
        """
        arg_value = getattr(parsed_args, item, None)
        if arg_value is not None:
            return arg_value
        return self.services.config.get(item)

    @staticmethod
    def _check_pro_requirement(
        pro_services: ProServices | None,
        run_managed: bool,  # noqa: FBT001
        is_managed: bool,  # noqa: FBT001
    ) -> None:
        craft_cli.emit.debug(
            f"pro_services: {pro_services}, run_managed: {run_managed}, is_managed: {is_managed}"
        )
        if pro_services is not None:  # should not be None for all lifecycle commands.
            # Validate requested pro services on the host if we are running in destructive mode.
            if not run_managed and not is_managed:
                craft_cli.emit.debug(
                    f"Validating requested Ubuntu Pro status on host: {pro_services}"
                )
                pro_services.validate()
            # Validate requested pro services running in managed mode inside a managed instance.
            elif run_managed and is_managed:
                craft_cli.emit.debug(
                    f"Validating requested Ubuntu Pro status in managed instance: {pro_services}"
                )
                pro_services.validate()
            # Validate pro attachment and service names on the host before starting a managed instance.
            elif run_managed and not is_managed:
                craft_cli.emit.debug(
                    f"Validating requested Ubuntu Pro attachment on host: {pro_services}"
                )
                pro_services.validate(
                    options=ValidatorOptions.AVAILABILITY | ValidatorOptions.SUPPORT
                )

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

        provider_name = command.provider_name(dispatcher.parsed_args())

        managed_mode = command.run_managed(dispatcher.parsed_args())

        # A ProServices instance will only be available for lifecycle commands,
        # which may consume pro packages,
        self._pro_services = getattr(dispatcher.parsed_args(), "pro", None)
        # Check that pro services are correctly configured if available
        self._check_pro_requirement(self._pro_services, managed_mode, self.is_managed())

        craft_cli.emit.debug(f"Build plan: platform={platform}, build_for={build_for}")
        self._pre_run(dispatcher)

        if managed_mode or command.needs_project(dispatcher.parsed_args()):
            self.services.project = self.get_project(
                platform=platform, build_for=build_for
            )

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
        self._initialize_craft_parts()

        craft_cli.emit.debug("Preparing application...")

        try:
            return_code = self._run_inner()
        except craft_cli.ArgumentParsingError as err:
            print(err, file=sys.stderr)  # to stderr, as argparse normally does
            craft_cli.emit.ended_ok()
            return_code = os.EX_USAGE
        except KeyboardInterrupt as err:
            self._emit_error(craft_cli.CraftError("Interrupted."), cause=err)
            return_code = 128 + signal.SIGINT
        except craft_cli.CraftError as err:
            self._emit_error(err)
            return_code = err.retcode
        except craft_parts.PartsError as err:
            self._emit_error(
                errors.PartsLifecycleError.from_parts_error(err),
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
        except Exception as err:
            self._emit_error(
                craft_cli.CraftError(f"{self.app.name} internal error: {err!r}"),
                cause=err,
            )
            if self.services.config.get("debug"):
                raise
            return_code = os.EX_SOFTWARE
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

    def _transform_project_yaml(
        self, yaml_data: dict[str, Any], build_on: str, build_for: str | None
    ) -> dict[str, Any]:
        """Update the project's yaml data with runtime properties.

        Performs task such as environment expansion. Note that this transforms
        ``yaml_data`` in-place.
        """
        # apply application-specific transformations first because an application may
        # add advanced grammar, project variables, or secrets to the yaml
        yaml_data = self._extra_yaml_transform(
            yaml_data, build_on=build_on, build_for=build_for
        )

        # At the moment there is no perfect solution for what do to do
        # expand project variables or to resolve the grammar if there's
        # no explicitly-provided target arch. However, we must resolve
        # it with *something* otherwise we might have an invalid parts
        # definition full of grammar declarations and incorrect build_for
        # architectures.
        build_for = build_for or build_on

        # Perform variable expansion.
        self._expand_environment(yaml_data=yaml_data, build_for=build_for)

        # Handle build secrets.
        if self.app.features.build_secrets:
            self._render_secrets(yaml_data)

        # Expand grammar.
        if "parts" in yaml_data:
            craft_cli.emit.debug(f"Processing grammar (on {build_on} for {build_for})")
            yaml_data["parts"] = grammar.process_parts(
                parts_yaml_data=yaml_data["parts"],
                arch=build_on,
                target_arch=build_for,
            )

        return yaml_data

    def _expand_environment(self, yaml_data: dict[str, Any], build_for: str) -> None:
        """Perform expansion of project environment variables.

        :param yaml_data: The project's yaml data.
        :param build_for: The architecture to build for.
        """
        if build_for == "all":
            build_for_arch = util.get_host_architecture()
            craft_cli.emit.debug(
                "Expanding environment variables with the host architecture "
                f"{build_for_arch!r} as the build-for architecture because 'all' was "
                "specified."
            )
        else:
            build_for_arch = build_for

        environment_vars = self._get_project_vars(yaml_data)
        project_dirs = craft_parts.ProjectDirs(
            work_dir=self._work_dir, partitions=self._partitions
        )

        info = craft_parts.ProjectInfo(
            application_name=self.app.name,  # not used in environment expansion
            cache_dir=pathlib.Path(),  # not used in environment expansion
            arch=build_for_arch,
            parallel_build_count=util.get_parallel_build_count(self.app.name),
            project_name=yaml_data.get("name", ""),
            project_dirs=project_dirs,
            project_vars=environment_vars,
            partitions=self._partitions,
        )

        self._set_global_environment(info)

        craft_parts.expand_environment(yaml_data, info=info)

    def _setup_partitions(self, yaml_data: dict[str, Any]) -> list[str] | None:
        """Return partitions to be used.

        When returning you will also need to ensure that the feature is enabled
        on Application instantiation craft_parts.Features(partitions_enabled=True)
        """
        _ = yaml_data
        return None

    def _get_project_vars(self, yaml_data: dict[str, Any]) -> dict[str, str]:
        """Return a dict with project variables to be expanded."""
        pvars: dict[str, str] = {}
        for var in self.app.project_variables:
            pvars[var] = str(yaml_data.get(var, ""))
        return pvars

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

    def _extra_yaml_transform(
        self,
        yaml_data: dict[str, Any],
        *,
        build_on: str,  # noqa: ARG002 (Unused method argument)
        build_for: str | None,  # noqa: ARG002 (Unused method argument)
    ) -> dict[str, Any]:
        """Perform additional transformations on a project's yaml data.

        Note: subclasses should return a new dict and keep the parameter unmodified.
        """
        return yaml_data

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


def filter_plan(
    build_plan: list[BuildInfo],
    platform: str | None,
    build_for: str | None,
    host_arch: str | None,
) -> list[BuildInfo]:
    """Filter out build plans that are not matching build-on, build-for, and platform.

    If the host_arch is None, ignore the build-on check for remote builds.
    """
    new_plan_matched_build_for: list[BuildInfo] = []
    new_plan_matched_platform_name: list[BuildInfo] = []

    for build_info in build_plan:
        if platform and build_info.platform != platform:
            continue

        if host_arch and build_info.build_on != host_arch:
            continue

        if build_for and build_info.build_for != build_for:
            continue

        if build_for and build_info.platform == build_for:
            # prioritize platform name if matched build_for
            new_plan_matched_platform_name.append(build_info)
            continue

        new_plan_matched_build_for.append(build_info)

    if new_plan_matched_platform_name:
        return new_plan_matched_platform_name
    return new_plan_matched_build_for
