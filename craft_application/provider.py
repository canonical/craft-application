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
"""Provider manager for craft-application."""
import functools
import os
import sys
from typing import Optional

import craft_providers
from craft_cli import CraftError, emit
from craft_providers import Provider
from craft_providers.actions.snap_installer import Snap
from craft_providers.bases import get_base_alias, get_base_from_alias
from craft_providers.lxd import LXDProvider, configure_buildd_image_remote
from craft_providers.multipass import MultipassProvider

from . import utils
from .errors import CraftEnvironmentError


class ProviderManager:
    """Manager for craft_providers in an application.

    :param app_name: the application name.
    :param provider_map: A mapping of provider names (e.g. 'lxd') to callables
        that return those providers.
    :param managed_mode_env: (Optional) a non-default environment variable for managed mode.
    :param provider_env: (Optional) an environment variable overriding the provider.
    """

    def __init__(
        self,
        app_name: str,
        *,
        managed_mode_env: Optional[str] = None,
        provider_env: Optional[str] = None,
    ) -> None:
        self.app_name = app_name
        self._app_upper = app_name.upper()
        self.managed_mode_env = managed_mode_env or f"{self._app_upper}_MANAGED_MODE"
        self.provider_env = provider_env or f"{self._app_upper}_PROVIDER"

    def _get_default_provider(self) -> Provider:
        """Get the default provider class to use for this application.

        :returns: An instance of the default Provider class.
        """
        if sys.platform == "linux":
            return self._provider_lxd
        return self._provider_multipass

    @functools.cached_property
    def is_managed(self) -> bool:
        """Determine whether we're running in managed mode."""
        return bool(utils.get_env_bool(self.managed_mode_env))

    def get_provider(self) -> Provider:
        """Get the provider to use."""
        if self.is_managed:
            raise CraftError("Cannot nest managed environments.")
        if self.provider_env not in os.environ:
            return self._get_default_provider()
        provider_name = os.environ[self.provider_env]
        if not hasattr(self, f"_provider_{provider_name}"):
            valid_providers = [k[10:] for k in dir(self) if k.startswith("_provider_")]
            raise CraftEnvironmentError(
                variable=self.provider_env,
                value=provider_name,
                valid_values=valid_providers,
            )
        emit.debug(
            f"Using provider {provider_name!r} from environment variable {self.provider_env}"
        )
        provider = getattr(self, f"_provider_{provider_name}")
        if not provider.is_provider_installed():
            auto_install = utils.confirm_with_user(
                f"Provider {provider_name} is not installed. Install now?",
                default=True,
            )
            if auto_install:
                provider.ensure_provider_is_available()
            else:
                raise CraftError(
                    f"Cannot proceed without {provider_name} installed.",
                    resolution=f"Install {provider_name} and run again.",
                )
        return provider

    def get_configuration(
        self,
        *,
        base: str,
        instance_name: str,
    ) -> craft_providers.Base:
        """Get the base configuration from a base name.

        :param base: The base to lookup.
        :param instance_name: A name to assign to the instance.

        This method should be overridden by a specific application if it intends to
        use base names that don't align to a "distro:version" naming convention.
        """
        distro, version = base.split(":", maxsplit=2)[:2]
        alias = get_base_alias((distro, version))
        base_class = get_base_from_alias(alias)
        return base_class(
            alias=alias,
            hostname=instance_name,
            snaps=[Snap(name=self.app_name, channel=None, classic=True)],
            environment={self.managed_mode_env: "1"},
        )

    @functools.cached_property
    def _provider_lxd(self) -> LXDProvider:
        """Get the LXD provider for this manager."""
        # TODO: Replace this deprecated function.
        # https://github.com/canonical/craft-providers/issues/260
        configure_buildd_image_remote()
        lxd_remote = os.getenv(f"{self._app_upper}_LXD_REMOTE", "local")
        return LXDProvider(lxd_project=self.app_name, lxd_remote=lxd_remote)

    @functools.cached_property
    def _provider_multipass(self) -> MultipassProvider:
        """Get the Multipass provider for this manager."""
        return MultipassProvider()
