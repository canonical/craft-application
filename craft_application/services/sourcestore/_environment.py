#  This file is part of craft-application.
#
#  Copyright 2026 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Determine which SD environment to use."""

from __future__ import annotations

import functools
import os

import pydantic
from craft_cli import CraftError


class SdEnvironment(pydantic.BaseModel, frozen=True):
    """Data about the environment we're using."""

    api_url: str
    dashboard_url: str
    git_url: str
    login_url: str
    source_store_credentials: str | None
    upstream_plane: str | None
    push_plane: str | None
    source_store_gateway: str
    publisher_gateway_url: str


_STAGING = SdEnvironment(
    api_url="https://api.staging.snapcraft.io",
    dashboard_url="https://dashboard.staging.snapcraft.io",
    git_url="https://git.staging.snapcraftcontent.com",
    login_url="https://login.staging.ubuntu.com",
    source_store_credentials=None,
    upstream_plane=None,
    push_plane=None,
    source_store_gateway="https://api.staging.pkg.store",
    publisher_gateway_url="https://api.staging.charmhub.io",
)

# Production uses all default values.
_PRODUCTION = SdEnvironment(
    api_url="https://api.snapcraft.io/",
    dashboard_url="https://dashboard.snapcraft.io",
    git_url="https://git.pkg.store/",
    login_url="https://login.ubuntu.com",
    source_store_credentials=None,
    upstream_plane=None,
    push_plane=None,
    source_store_gateway="https://api.pkg.store",
    publisher_gateway_url="https://api.charmhub.io",
)

ENV_VARS = SdEnvironment(
    api_url="CRAFT_API_URL",
    dashboard_url="STORE_DASHBOARD_URL",
    git_url="CRAFT_SOURCE_STORE_GIT_URL",
    login_url="UBUNTU_ONE_SSO_URL",
    source_store_credentials="CRAFT_SOURCE_STORE_CREDENTIALS",
    upstream_plane="CRAFT_SOURCE_STORE_PLANE",
    push_plane="CRAFT_SOURCE_STORE_PLANE",
    source_store_gateway="CRAFT_SOURCE_STORE_GATEWAY",
    publisher_gateway_url="STORE_PUBLISHER_GW",
)
"""The environment variables that can be used to modify an environment.

If a field is set to an empty string, the field will be ignored.
"""


@functools.lru_cache(maxsize=1)
def get_sd_environment() -> SdEnvironment:
    """Get the SD environment to use.

    This checks the `CRAFT_SD_ENV` environment variable. If it's unset, it defaults to
    the default environment. Otherwise, it uses either the provided environment name
    or reads the environment variable as a JSON string and sets up the values as needed.

    Existing environment variables can then be used to override single values if needed.
    """
    # Currently we default to staging as there is no prod.
    sd_env = os.getenv("CRAFT_SD_ENV", "STAGING")

    # Get the base set of SD URLs
    match sd_env.lower():
        case "production" | "prod":
            base_environment = _PRODUCTION
        case "staging":
            base_environment = _STAGING
        case _:
            try:
                base_environment = SdEnvironment.model_validate_json(sd_env)
            except pydantic.ValidationError:
                base_environment = _STAGING
                raise CraftError(
                    message="Invalid value for CRAFT_SD_ENV.",
                    resolution=(
                        "CRAFT_SD_ENV must be one of 'PROD', 'STAGING', or a JSON object with the following fields:\n"
                        f"{list(SdEnvironment.model_fields)}"
                    ),
                    reportable=False,
                )

    # Apply any overrides from environment variables
    overrides: dict[str, str] = {}
    for var, env_var in ENV_VARS.model_dump().items():
        if not env_var:
            continue
        if (env_value := os.environ.get(env_var)) is not None:
            overrides[var] = env_value
    environment_dict = base_environment.model_dump() | overrides

    return SdEnvironment.model_validate(environment_dict)
