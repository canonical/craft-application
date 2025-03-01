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
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""OS and architecture helpers for craft applications."""

from __future__ import annotations

import functools
import os
import platform
from typing import Final

from craft_parts.utils import os_utils
from craft_providers import bases

from .string import strtobool

ENVIRONMENT_CRAFT_MANAGED_MODE: Final[str] = "CRAFT_MANAGED_MODE"


@functools.lru_cache(maxsize=1)
def get_host_architecture() -> str:
    """Get host architecture in deb format."""
    machine = platform.machine()
    return _ARCH_TRANSLATIONS_PLATFORM_TO_DEB.get(machine, machine)


def convert_architecture_deb_to_platform(arch: str) -> str:
    """Convert an architecture from deb/snap syntax to platform syntax.

    :param architecture: architecture string in debian/snap syntax
    :return: architecture in platform syntax
    """
    return _ARCH_TRANSLATIONS_DEB_TO_PLATFORM.get(arch, arch)


def is_valid_architecture(arch: str) -> bool:
    """Check if a debian-syntax architecture is valid."""
    return arch in _ARCH_TRANSLATIONS_DEB_TO_PLATFORM


@functools.lru_cache(maxsize=1)
def get_host_base() -> bases.BaseName:
    """Get the craft-providers base for the running host."""
    release = os_utils.OsRelease()
    os_id = release.id()
    version_id = release.version_id()
    return bases.BaseName(os_id, version_id)


def get_hostname(hostname: str | None = None) -> str:
    """Return the computer's network name or UNNKOWN if it cannot be determined."""
    if hostname is None:
        hostname = platform.node()
    hostname = hostname.strip()
    if not hostname:
        hostname = "UNKNOWN"
    return hostname


def is_managed_mode() -> bool:
    """Check if craft is running in a managed environment."""
    managed_flag = os.getenv(ENVIRONMENT_CRAFT_MANAGED_MODE, "n")
    return strtobool(managed_flag)


# architecture translations from the platform syntax to the deb/snap syntax
# These two architecture mappings are almost inverses of each other, except one map is
# not reversible (same value for different keys)
_ARCH_TRANSLATIONS_PLATFORM_TO_DEB = {
    "aarch64": "arm64",
    "armv7l": "armhf",
    "i686": "i386",
    "ppc": "powerpc",
    "ppc64le": "ppc64el",
    "x86_64": "amd64",
    "AMD64": "amd64",  # Windows support
    "s390x": "s390x",
    "riscv64": "riscv64",
}

# architecture translations from the deb/snap syntax to the platform syntax
_ARCH_TRANSLATIONS_DEB_TO_PLATFORM = {
    "arm64": "aarch64",
    "armhf": "armv7l",
    "i386": "i686",
    "powerpc": "ppc",
    "ppc64el": "ppc64le",
    "amd64": "x86_64",
    "s390x": "s390x",
    "riscv64": "riscv64",
}
