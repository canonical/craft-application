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
import io
import os
import pathlib
import pkgutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from craft_cli import CraftError, emit
from craft_providers import bases
from craft_providers.actions.snap_installer import Snap
from craft_providers.lxd import LXDProvider
from craft_providers.multipass import MultipassProvider

from craft_application import util
from craft_application.services import base
from craft_application.util import platforms, snap_config

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Generator

    import craft_providers

    from craft_application import models
    from craft_application.application import AppMetadata
    from craft_application.services import ServiceFactory


DEFAULT_FORWARD_ENVIRONMENT_VARIABLES = ("http_proxy", "https_proxy", "no_proxy")


class ProviderService(base.ProjectService):
    """Manager for craft_providers in an application.

    :param app: Metadata about this application.
    :param project: The project model
    :param install_snap: Whether to install this app's snap from the host (default True)
    """

    managed_mode_env_var = "CRAFT_MANAGED_MODE"

    def __init__(
        self,
        app: AppMetadata,
        services: ServiceFactory,
        *,
        project: models.Project,
        work_dir: pathlib.Path,
        build_plan: list[models.BuildInfo],
        provider_name: str | None = None,
        install_snap: bool = True,
    ) -> None:
        super().__init__(app, services, project=project)
        self._provider: craft_providers.Provider | None = None
        self._work_dir = work_dir
        self._build_plan = build_plan
        self.snaps: list[Snap] = []
        if install_snap:
            self.snaps.append(Snap(name=app.name, channel=None, classic=True))
        self.environment: dict[str, str | None] = {self.managed_mode_env_var: "1"}
        self.packages: list[str] = []
        # this is a private attribute because it may not reflect the actual
        # provider name. Instead, self._provider.name should be used.
        self.__provider_name: str | None = provider_name

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

    @contextlib.contextmanager
    def instance(
        self,
        build_info: models.BuildInfo,
        *,
        work_dir: pathlib.Path,
        allow_unstable: bool = True,
        **kwargs: bool | str | None,
    ) -> Generator[craft_providers.Executor, None, None]:
        """Context manager for getting a provider instance.

        :param base_name: A craft_providers capable base name (tuple of name, version)
        :param work_dir: Local path to mount inside the provider instance.
        :param allow_unstable: Whether to allow the use of unstable images.
        :returns: a context manager of the provider instance.
        """
        instance_name = self._get_instance_name(work_dir, build_info)
        emit.debug(f"Preparing managed instance {instance_name!r}")
        base_name = build_info.base
        base = self.get_base(base_name, instance_name=instance_name, **kwargs)
        provider = self.get_provider(name=self.__provider_name)

        emit.progress(f"Launching managed {base_name[0]} {base_name[1]} instance...")
        with provider.launched_environment(
            project_name=self._project.name,
            project_path=work_dir,
            instance_name=instance_name,
            base_configuration=base,
            allow_unstable=allow_unstable,
        ) as instance:
            instance.mount(
                host_source=work_dir,
                # Ignore argument type until craft-providers accepts PurePosixPaths
                # https://github.com/canonical/craft-providers/issues/315
                target=self._app.managed_instance_project_path,  # type: ignore[arg-type]
            )
            emit.debug("Instance launched and working directory mounted")
            self._setup_instance_bashrc(instance)
            try:
                with emit.pause():
                    yield instance
            finally:
                self._capture_logs_from_instance(instance)

    def get_base(
        self,
        base_name: bases.BaseName | tuple[str, str],
        *,
        instance_name: str,
        **kwargs: bool | str | None,
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
            alias=alias,
            compatibility_tag=f"{self._app.name}-{base_class.compatibility_tag}",
            hostname=instance_name,
            snaps=self.snaps,
            environment=self.environment,
            packages=self.packages,
            **kwargs,  # type: ignore[arg-type]
        )

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

        # (2) get the provider from the environment (CRAFT_BUILD_ENVIRONMENT),
        elif env_provider := os.getenv("CRAFT_BUILD_ENVIRONMENT"):
            emit.debug(f"Using provider {env_provider!r} from environment.")
            chosen_provider = env_provider

        # (3) use provider specified with snap configuration,
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

        current_arch = platforms.get_host_architecture()
        build_plan = [
            info for info in self._build_plan if info.build_on == current_arch
        ]

        if build_plan:
            target = "environments" if len(build_plan) > 1 else "environment"
            emit.progress(f"Cleaning build {target}")

        for info in build_plan:
            instance_name = self._get_instance_name(self._work_dir, info)
            emit.debug(f"Cleaning instance {instance_name}")
            provider.clean_project_environments(instance_name=instance_name)

    def _get_instance_name(
        self, work_dir: pathlib.Path, build_info: models.BuildInfo
    ) -> str:
        work_dir_inode = work_dir.stat().st_ino
        return (
            f"{self._app.name}-{self._project.name}-on-{build_info.build_on}-"
            f"for-{build_info.build_for}-{work_dir_inode}"
        )

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
        lxd_remote = os.getenv("CRAFT_LXD_REMOTE", "local")
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
                    for line in log_file:
                        emit.debug(":: " + line.rstrip())
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
