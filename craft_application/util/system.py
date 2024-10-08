# This file is part of craft-application.
#
# Copyright 2024 Canonical Ltd.
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
"""System-level util functions."""
from __future__ import annotations

import os

from craft_cli import emit

from craft_application.errors import InvalidParameterError


def _verify_parallel_build_count(env_name: str, parallel_build_count: int | str) -> int:
    """Verify the parallel build count is valid.

    :param env_name: The name of the environment variable being checked.
    :param parallel_build_count: The value of the variable.
    :return: The parallel build count as an integer.
    """
    try:
        parallel_build_count = int(parallel_build_count)
    except ValueError as err:
        raise InvalidParameterError(env_name, str(os.environ[env_name])) from err

    # Ensure the value is valid positive integer
    if parallel_build_count < 1:
        raise InvalidParameterError(env_name, str(parallel_build_count))

    return parallel_build_count


def get_parallel_build_count(app_name: str) -> int:
    """Get the number of parallel builds to run.

    The parallel build count is determined by the first available of the
    following environment variables in the order:

    - <APP_NAME>_PARALLEL_BUILD_COUNT
    - CRAFT_PARALLEL_BUILD_COUNT
    - <APP_NAME>_MAX_PARALLEL_BUILD_COUNT
    - CRAFT_MAX_PARALLEL_BUILD_COUNT

    where the MAX_PARALLEL_BUILD_COUNT variables are dynamically compared to
    the number of CPUs, and the smaller of the two is used.

    If no environment variable is set, the CPU count is used.
    If the CPU count is not available for some reason, 1 is used as a fallback.
    """
    parallel_build_count = None

    # fixed parallel build count environment variable
    for env_name in [
        (app_name + "_PARALLEL_BUILD_COUNT").upper(),
        "CRAFT_PARALLEL_BUILD_COUNT",
    ]:
        if os.environ.get(env_name):
            parallel_build_count = _verify_parallel_build_count(
                env_name, os.environ[env_name]
            )
            emit.debug(
                f"Using parallel build count of {parallel_build_count} "
                f"from environment variable {env_name!r}"
            )
            break

    # CPU count related max parallel build count environment variable
    if parallel_build_count is None:
        cpu_count = os.cpu_count() or 1
        for env_name in [
            (app_name + "_MAX_PARALLEL_BUILD_COUNT").upper(),
            "CRAFT_MAX_PARALLEL_BUILD_COUNT",
        ]:
            if os.environ.get(env_name):
                parallel_build_count = min(
                    cpu_count,
                    _verify_parallel_build_count(env_name, os.environ[env_name]),
                )
                emit.debug(
                    f"Using parallel build count of {parallel_build_count} "
                    f"from environment variable {env_name!r}"
                )
                break

        # Default to CPU count if no max environment variable is set
        if parallel_build_count is None:
            parallel_build_count = cpu_count
            emit.debug(
                f"Using parallel build count of {parallel_build_count} "
                "from CPU count"
            )

    return parallel_build_count
