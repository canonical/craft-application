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
"""Authentication implementation for the SourceStore client."""

import platform

from craft_cli import emit

from ._environment import get_sd_environment


def prompt_login() -> tuple[str, str]:
    """Prompt for login credentials for Ubuntu One."""
    emit.progress("Enter your Ubuntu One e-mail address and password.", permanent=True)
    emit.progress(
        "If you do not have an Ubuntu One account, you can create one "
        f"at {get_store_login_url()}",
        permanent=True,
    )
    email = emit.prompt("Email: ")
    password = emit.prompt("Password: ", hide=True)

    return (email, password)


def build_user_agent(
    *,
    app_name: str,
    version: str = "0,0.0",
) -> str:
    """Build user agent used for UbuntuOne login."""
    return f"{app_name}/{version}/{_ua_system_info()}"


def _ua_system_info() -> str:
    """System information for user agent.

    Borrowed from charmcraft.
    """
    segments = [
        f"{platform.system()} {platform.release()}",
        platform.machine(),
        f"{platform.python_implementation()} {platform.python_version()}",
    ]
    if platform.system() == "Linux":
        import distro  # noqa: PLC0415

        segments.append(f"{distro.name()} {distro.version()}")

    return "; ".join(segments)


def get_store_login_url() -> str:
    """Return the Ubuntu Login URL considering the environment.

    This is only useful when using Ubuntu One SSO.
    """
    return get_sd_environment().login_url


def get_store_url() -> str:
    """Return the Store URL considering the environment."""
    return get_sd_environment().dashboard_url


def get_publisher_gateway_url() -> str:
    """Return the publisher gateway URL considering the environment."""
    return get_sd_environment().publisher_gateway_url
