#  This file is part of craft-application.
#
#  Copyright 2023-2024 Canonical Ltd.
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
"""Service class for craft-providers."""

from __future__ import annotations

import contextlib
import enum
import io
import os
import pathlib
import pkgutil
import subprocess
import sys
import urllib.request
from pathlib import Path
from typing import TYPE_CHECKING

import craft_platforms
import craft_providers
from craft_cli import CraftError, emit
from craft_providers import bases
from craft_providers.actions.snap_installer import Snap
from craft_providers.lxd import LXDProvider
from craft_providers.multipass import MultipassProvider

from craft_application import models, util
from craft_application.services import base
from craft_application.util import platforms, snap_config

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable, Generator, Iterable, Sequence

    from craft_application.application import AppMetadata
    from craft_application.services import ServiceFactory


DEFAULT_FORWARD_ENVIRONMENT_VARIABLES: Iterable[str] = ()
IGNORE_CONFIG_ITEMS: Iterable[str] = ("build_for", "platform", "verbosity_level")

_REQUESTED_SNAPS: dict[str, Snap] = {}
"""Additional snaps to be installed using provider."""


class ProviderService(base.AppService):
    """Manager for craft_providers in an application.

    :param app: Metadata about this application.
    :param project: The project model
    :param install_snap: Whether to install this app's snap from the host (default True)
    """

    managed_mode_env_var = platforms.ENVIRONMENT_CRAFT_MANAGED_MODE

    def __init__(
        self,
        app: AppMetadata,
        services: ServiceFactory,
        *,
        work_dir: pathlib.Path,
        provider_name: str | None = None,
        install_snap: bool = True,
    ) -> None:
        super().__init__(app, services)
        self._provider: craft_providers.Provider | None = None
        self._work_dir = work_dir
        self.snaps: list[Snap] = []
        self._install_snap = install_snap
        self.environment: dict[str, str | None] = {self.managed_mode_env_var: "1"}
        self.packages: list[str] = []
        # this is a private attribute because it may not reflect the actual
        # provider name. Instead, self._provider.name should be used.
        self.__provider_name: str | None = provider_name
        self._pack_state: models.PackState = models.PackState(
            artifact=None, resources=None
        )

    @property
    def compatibility_tag(self) -> str:
        """Get craft-application's suffix for the compatibility tag."""
        return ".1"

    @classmethod
    def is_managed(cls) -> bool:
        """Determine whether we're running in managed mode."""
        return os.getenv(cls.managed_mode_env_var) == "1"

    def setup(self) -> None:
        """Application-specific service setup."""
        super().setup()
        for name in DEFAULT_FORWARD_ENVIRONMENT_VARIABLES:
            if name in os.environ:
                self.environment[name] = os.getenv(name)

        app_upper = self._app.name.upper()
        for config_item, value in self._services.get("config").get_all().items():
            if config_item in IGNORE_CONFIG_ITEMS or value is None:
                continue
            value_out = value.name if isinstance(value, enum.Enum) else str(value)
            self.environment[f"{app_upper}_{config_item.upper()}"] = value_out

        for scheme, value in urllib.request.getproxies().items():
            self.environment[f"{scheme.lower()}_proxy"] = value
            self.environment[f"{scheme.upper()}_PROXY"] = value

        if self._install_snap:
            self.snaps.extend(_REQUESTED_SNAPS.values())

            if util.is_running_from_snap(self._app.name):
                # use the aliased name of the snap when injecting
                name = os.getenv("SNAP_INSTANCE_NAME", self._app.name)
                channel = None
                emit.debug(
                    f"Setting {self._app.name} to be injected from the "
                    "host into the build environment because it is running "
                    "as a snap."
                )
            else:
                # use the snap name when installing from the store
                name = self._app.name
                channel = os.getenv("CRAFT_SNAP_CHANNEL", "latest/stable")
                emit.debug(
                    f"Setting {self._app.name} to be installed from the {channel} "
                    "channel in the build environment because it is not running "
                    "as a snap."
                )

            self.snaps.append(Snap(name=name, channel=channel, classic=True))

    @contextlib.contextmanager
    def instance(
        self,
        build_info: craft_platforms.BuildInfo,
        *,
        work_dir: pathlib.Path,
        allow_unstable: bool = True,
        clean_existing: bool = False,
        use_base_instance: bool = True,
        project_name: str | None = None,
        prepare_instance: Callable[[craft_providers.Executor], None] | None = None,
        **kwargs: bool | str | None,
    ) -> Generator[craft_providers.Executor, None, None]:
        """Context manager for getting a provider instance.

        :param build_info: Build information for the instance.
        :param work_dir: Local path to mount inside the provider instance.
        :param allow_unstable: Whether to allow the use of unstable images.
        :param clean_existing: Whether pre-existing instances should be wiped
          and re-created.
        :param use_base_instance: Whether we should copy the instance from a
          base instance, if the provider offers that possibility.
        :returns: a context manager of the provider instance.
        """
        if not project_name:
            project_name = self._project.name
        instance_name = self._get_instance_name(work_dir, build_info, project_name)
        emit.debug(f"Preparing managed instance {instance_name!r}")
        base_name = bases.BaseName(
            name=build_info.build_base.distribution,
            version=build_info.build_base.series,
        )
        base = self.get_base(base_name, instance_name=instance_name, **kwargs)
        provider = self.get_provider(name=self.__provider_name)

        provider.ensure_provider_is_available()
        shutdown_delay = self._services.get("config").get("idle_mins")

        if clean_existing:
            self._clean_instance(provider, work_dir, build_info, project_name)

        emit.progress(f"Launching managed {base_name[0]} {base_name[1]} instance...")
        with provider.launched_environment(
            project_name=project_name,
            project_path=work_dir,
            instance_name=instance_name,
            base_configuration=base,
            allow_unstable=allow_unstable,
            use_base_instance=use_base_instance,
            prepare_instance=prepare_instance,
            shutdown_delay_mins=shutdown_delay,
        ) as instance:
            instance.mount(
                host_source=work_dir,
                # Ignore argument type until craft-providers accepts PurePosixPaths
                # https://github.com/canonical/craft-providers/issues/315
                target=self._app.managed_instance_project_path,  # type: ignore[arg-type]
            )
            self._services.get("state").configure_instance(instance)
            emit.debug("Instance launched and working directory mounted")
            self._setup_instance_bashrc(instance)
            try:
                yield instance
            finally:
                self._capture_logs_from_instance(instance)

    def get_base(
        self,
        base_name: bases.BaseName,
        *,
        instance_name: str,
        **kwargs: bool | str | pathlib.Path | None,
    ) -> craft_providers.Base:
        """Get the base configuration from a base name.

        :param base_name: The base to lookup.
        :param instance_name: A name to assign to the instance.
        :param kwargs: Additional keyword arguments are sent directly to the base.

        This method should be overridden by a specific application if it intends to
        use base names that don't align to a "distro:version" naming convention.
        """
        alias = bases.get_base_alias(base_name)
        base_class = bases.get_base_from_alias(alias)
        if base_class is bases.BuilddBase:
            # These packages are required on the base system (provider) for
            # the Package Repositories feature from Craft Archives to work.
            # This is only doable here where we have access to the base, as
            # this only applies to our Buildd images (i.e.; Ubuntu)
            self.packages.extend(["gpg", "dirmngr"])
        return base_class(
            alias=alias,  # type: ignore[arg-type]
            compatibility_tag=f"{self._app.name}-{base_class.compatibility_tag}{self.compatibility_tag}",
            hostname=instance_name,
            snaps=self.snaps,
            environment=self.environment,
            packages=self.packages,
            **kwargs,  # type: ignore[arg-type]
        )

    def get_pack_state(self) -> models.PackState:
        """Get packaging state information."""
        return self._pack_state

    def get_provider(self, name: str | None = None) -> craft_providers.Provider:
        """Get the provider to use.

        :param name: if set, uses the given provider name.

        The provider is determined in the following order:
        (1) use provider specified in the function argument,
        (2) get the provider from the environment (CRAFT_BUILD_ENVIRONMENT),
        (3) use provider specified with snap configuration,
        (4) default to platform default (LXD on Linux, otherwise Multipass).

        :returns: The Provider to use.

        :raises CraftError: If already running in managed mode.
        """
        if self._provider is not None:
            return self._provider

        if self.is_managed():
            raise CraftError("Cannot nest managed environments.")

        # (1) use provider specified in the function argument,
        if name:
            emit.debug(f"Using provider {name!r} passed as an argument.")
            chosen_provider: str = name

        # (2) get the provider from build_environment
        elif provider := self._services.config.get("build_environment"):
            emit.debug(f"Using provider {provider!r} from system configuration.")
            chosen_provider = provider

        # (3) use provider specified in snap configuration
        elif snap_provider := self._get_provider_from_snap_config():
            emit.debug(f"Using provider {snap_provider!r} from snap config.")
            chosen_provider = snap_provider

        # (4) default to platform default (LXD on Linux, otherwise Multipass)
        elif sys.platform == "linux":
            emit.debug("Using default provider 'lxd' on linux system.")
            chosen_provider = "lxd"
        else:
            emit.debug("Using default provider 'multipass' on non-linux system.")
            chosen_provider = "multipass"

        self._provider = self._get_provider_by_name(chosen_provider)
        return self._provider

    def _get_provider_from_snap_config(self) -> str | None:
        """Get the provider stored in the snap config.

        :returns: The provider name or None if the app doesn't support a snap
        config or doesn't have a provider set in the snap config.
        """
        config = snap_config.get_snap_config(app_name=self._app.name)

        if config is None:
            emit.debug("No snap config found.")
            return None

        try:
            return config.provider
        except AttributeError:
            emit.debug("Provider not set in snap config.")
            return None

    def clean_instances(self) -> None:
        """Clean all existing managed instances related to the project."""
        provider = self.get_provider(name=self.__provider_name)
        build_planner = self._services.get("build_plan")

        build_plan = build_planner.create_build_plan(
            platforms=None,
            build_for=None,
            build_on=[craft_platforms.DebianArchitecture.from_host()],
        )

        if build_plan:
            target = "environments" if len(build_plan) > 1 else "environment"
            emit.progress(f"Cleaning build {target}")

        for info in build_plan:
            self._clean_instance(provider, self._work_dir, info, self._project.name)

    def _get_instance_name(
        self,
        work_dir: pathlib.Path,
        build_info: craft_platforms.BuildInfo,
        project_name: str,
    ) -> str:
        work_dir_inode = work_dir.stat().st_ino

        # craft-providers will remove invalid characters from the name but replacing
        # characters improves readability for multi-base platforms like "ubuntu@24.04:amd64"
        platform = build_info.platform.replace(":", "-").replace("@", "-")

        return f"{self._app.name}-{project_name}-{platform}-{work_dir_inode}"

    def _get_provider_by_name(self, name: str) -> craft_providers.Provider:
        """Get a provider by its name."""
        # normalize the name
        normalized_name = name.lower().strip()

        if normalized_name == "lxd":
            return self._get_lxd_provider()
        if normalized_name == "multipass":
            return self._get_multipass_provider()
        raise RuntimeError(f"Unknown provider: {name!r}")

    def _get_lxd_provider(self) -> LXDProvider:
        """Get the LXD provider for this manager."""
        lxd_remote = self._services.config.get("lxd_remote")
        return LXDProvider(lxd_project=self._app.name, lxd_remote=lxd_remote)

    def _get_multipass_provider(self) -> MultipassProvider:
        """Get the Multipass provider for this manager."""
        return MultipassProvider()

    def _capture_logs_from_instance(self, instance: craft_providers.Executor) -> None:
        """Fetch the logfile from inside `instance` and emit its contents."""
        source_log_path = util.get_managed_logpath(self._app)
        with instance.temporarily_pull_file(
            source=source_log_path, missing_ok=True
        ) as log_path:
            if log_path:
                emit.debug("Logs retrieved from managed instance:")
                with log_path.open() as log_file:
                    emit.append_to_log(file=log_file)
            else:
                emit.debug(
                    f"Could not find log file {source_log_path.as_posix()} in instance."
                )

    def _setup_instance_bashrc(self, instance: craft_providers.Executor) -> None:
        """Set up the instance's bashrc to export environment."""
        bashrc = pkgutil.get_data("craft_application", "misc/instance_bashrc")

        if bashrc is None:
            emit.debug(
                "Could not find the bashrc file in the craft-application package"
            )
            return

        emit.debug("Pushing bashrc to instance")
        instance.push_file_io(
            destination=Path("/root/.bashrc"),
            content=io.BytesIO(bashrc),
            file_mode="644",
        )

    def _clean_instance(
        self,
        provider: craft_providers.Provider,
        work_dir: pathlib.Path,
        info: craft_platforms.BuildInfo,
        project_name: str,
    ) -> None:
        """Clean an instance, if it exists."""
        instance_name = self._get_instance_name(work_dir, info, project_name)
        emit.debug(f"Cleaning instance {instance_name}")
        provider.clean_project_environments(instance_name=instance_name)

    @classmethod
    def register_snap(cls, name: str, snap: Snap) -> None:
        """Register new snap for installation in provider instance."""
        _REQUESTED_SNAPS[name] = snap

    @classmethod
    def unregister_snap(cls, name: str) -> None:
        """Unregister snap from installation."""
        try:
            del _REQUESTED_SNAPS[name]
        except KeyError:
            raise ValueError(f"Snap not registered: {name!r}")

    def run_managed(
        self,
        build_info: craft_platforms.BuildInfo,
        enable_fetch_service: bool,  # noqa: FBT001
        command: Sequence[str] = (),
    ) -> None:
        """Create a managed instance and run a command in it.

        :param build_info: The BuildInfo that defines what instance to use.
        :enable_fetch_service: Whether to enable the fetch service.
        :command: The command to run. Defaults to the current command.
        """
        if not command:
            command = [self._app.name, *sys.argv[1:]]
        env = {
            "CRAFT_PLATFORM": build_info.platform,
            "CRAFT_VERBOSITY_LEVEL": emit.get_mode().name,
        }
        emit.debug(
            f"Running managed {self._app.name} in managed {build_info.build_base} instance for platform {build_info.platform!r}"
        )

        active_fetch_service = self._services.get_class("fetch").is_active(
            enable_command_line=enable_fetch_service
        )
        emit.debug(f"active_fetch_service={active_fetch_service}")

        def prepare_instance(instance: craft_providers.Executor) -> None:
            emit.debug("Preparing instance")
            if active_fetch_service:
                fetch_env = self._services.get("fetch").configure_instance(instance)
                env.update(fetch_env)

            session_env = self._services.get("proxy").configure_instance(instance)
            env.update(session_env)

        with self.instance(
            build_info=build_info,
            work_dir=self._work_dir,
            clean_existing=active_fetch_service,
            prepare_instance=prepare_instance,
            use_base_instance=not active_fetch_service,
        ) as instance:
            emit.debug(f"Running in instance: {command}")
            self._services.get("proxy").finalize_instance_configuration(instance)
            try:
                with emit.pause():
                    # Pyright doesn't fully understand craft_providers's CompletedProcess.
                    instance.execute_run(  # pyright: ignore[reportUnknownMemberType,reportUnknownVariableType]
                        list(command),
                        cwd=self._app.managed_instance_project_path,
                        check=True,
                        env=env,
                    )
            except subprocess.CalledProcessError as exc:
                raise craft_providers.ProviderError(
                    f"Failed to run {self._app.name} in instance"
                ) from exc
            finally:
                if active_fetch_service:
                    self._services.get("fetch").teardown_instance()
