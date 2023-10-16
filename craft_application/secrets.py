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
"""Handling of build-time secrets."""
from __future__ import annotations

import re
import subprocess
from typing import Any

from craft_application import errors

SECRET_REGEX = re.compile(r"\$\(HOST_SECRET:(?P<command>.*)\)")


def render_secrets(yaml_data: dict[str, Any]) -> set[str]:
    """Render/expand the build secrets in a project's yaml data (in-place).

    This function will process directives of the form $(HOST_SECRET:<cmd>) in string
    values in ``yaml_data``. For each such directive, the <cmd> part is executed (with
    bash) and the resulting output replaces the whole directive. The returned set
    contains the outputs of all HOST_SECRET processing (for masking with craft-cli).

    Note that only a few fields are currently supported:

    - "source" and "build-environment" for parts.

    Using HOST_SECRET directives in any other field is an error.
    """
    command_cache: dict[str, str] = {}

    # Process the fields where we allow build secrets
    parts = yaml_data.get("parts", {})
    for part in parts.values():
        _render_part_secrets(part, command_cache)

    # Now loop over all the data to check for build secrets in disallowed fields
    _check_for_secrets(yaml_data)

    return set(command_cache.values())


def _render_part_secrets(
    part_data: dict[str, Any], command_cache: dict[str, Any]
) -> None:
    # Render "source"
    source = part_data.get("source", "")
    if (rendered := _render_secret(source, command_cache)) is not None:
        part_data["source"] = rendered

    # Render "build-environment"
    build_env = part_data.get("build-environment", [])
    # "build-environment" is a list of dicts with a single item each
    for single_entry_dict in build_env:
        for var_name, var_value in single_entry_dict.items():
            if (rendered := _render_secret(var_value, command_cache)) is not None:
                single_entry_dict[var_name] = rendered


def _render_secret(text: str, command_cache: dict[str, str]) -> str | None:
    if match := SECRET_REGEX.search(text):
        command = match.group("command")
        host_directive = match.group(0)

        if command in command_cache:
            output = command_cache[command]
        else:
            try:
                output = _run_command(command)
            except subprocess.CalledProcessError as err:
                raise errors.SecretsCommandError(
                    host_directive, err.stderr.decode()
                ) from err
            command_cache[command] = output

        return text.replace(host_directive, output)
    return None


def _run_command(command: str) -> str:
    bash_command = f"set -euo pipefail; {command}"
    return (
        subprocess.check_output(["bash", "-c", bash_command], stderr=subprocess.PIPE)
        .decode("utf-8")
        .strip()
    )


# pyright: reportUnknownVariableType=false,reportUnknownArgumentType=false
def _check_for_secrets(data: Any) -> None:  # noqa: ANN401 (using Any on purpose)
    if isinstance(data, dict):
        for key, value in data.items():
            _check_str(value, field_name=key)
            if isinstance(value, list):
                for item in value:
                    _check_str(item, field_name=key)
                    _check_for_secrets(item)
            elif isinstance(value, dict):
                _check_for_secrets(value)


def _check_str(
    value: Any, field_name: str  # noqa: ANN401 (using Any on purpose)
) -> None:
    if isinstance(value, str) and (match := SECRET_REGEX.search(value)):
        raise errors.SecretsFieldError(host_secret=match.group(), field_name=field_name)
