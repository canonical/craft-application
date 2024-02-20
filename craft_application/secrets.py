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

import base64
import dataclasses
import json
import os
import re
import subprocess
from collections.abc import Mapping
from typing import Any, cast

from craft_application import errors

SECRET_REGEX = re.compile(r"\$\(HOST_SECRET:(?P<command>.*)\)")


@dataclasses.dataclass(frozen=True)
class BuildSecrets:
    """The data needed to correctly handle build-time secrets in the application."""

    environment: dict[str, str]
    """The encoded information that can be passed to a managed instance's environment."""

    secret_strings: set[str]
    """The actual secret text strings, to be passed to craft_cli."""


def render_secrets(yaml_data: dict[str, Any], *, managed_mode: bool) -> BuildSecrets:
    """Render/expand the build secrets in a project's yaml data (in-place).

    This function will process directives of the form $(HOST_SECRET:<cmd>) in string
    values in ``yaml_data``. For each such directive, the <cmd> part is executed (with
    bash) and the resulting output replaces the whole directive. The returned object
    contains the result of HOST_SECRET processing (for masking with craft-cli and
    forwarding to managed instances).

    Note that only a few fields are currently supported:

    - "source" and "build-environment" for parts.

    Using HOST_SECRET directives in any other field is an error.

    :param yaml_data: The project's loaded data
    :param managed_mode: Whether the current application is running in managed mode.
    """
    command_cache: dict[str, str] = {}

    if managed_mode:
        command_cache = _decode_commands(os.environ)

    # Process the fields where we allow build secrets
    parts = yaml_data.get("parts", {})
    for part in parts.values():
        _render_part_secrets(part, command_cache, managed_mode)

    # Now loop over all the data to check for build secrets in disallowed fields
    _check_for_secrets(yaml_data)

    return BuildSecrets(
        environment=_encode_commands(command_cache),
        secret_strings=set(command_cache.values()),
    )


def _render_part_secrets(
    part_data: dict[str, Any],
    command_cache: dict[str, Any],
    managed_mode: bool,  # noqa: FBT001 (boolean positional arg)
) -> None:
    # Render "source"
    source = part_data.get("source", "")
    if (rendered := _render_secret(source, command_cache, managed_mode)) is not None:
        part_data["source"] = rendered

    # Render "build-environment"
    build_env = part_data.get("build-environment", [])
    # "build-environment" is a list of dicts with a single item each
    for single_entry_dict in build_env:
        for var_name, var_value in single_entry_dict.items():
            rendered = _render_secret(var_value, command_cache, managed_mode)
            if rendered is not None:
                single_entry_dict[var_name] = rendered


def _render_secret(
    yaml_string: str,
    command_cache: dict[str, str],
    managed_mode: bool,  # noqa: FBT001 (boolean positional arg)
) -> str | None:
    if match := SECRET_REGEX.search(yaml_string):
        command = match.group("command")
        host_directive = match.group(0)

        if command in command_cache:
            output = command_cache[command]
        else:
            if managed_mode:
                # In managed mode the command *must* be in the cache; this is an error.
                raise errors.SecretsManagedError(host_directive)

            try:
                output = _run_command(command)
            except subprocess.CalledProcessError as err:
                raise errors.SecretsCommandError(
                    host_directive, err.stderr.decode()
                ) from err
            command_cache[command] = output

        return yaml_string.replace(host_directive, output)
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
        raise errors.SecretsFieldError(
            host_directive=match.group(), field_name=field_name
        )


def _encode_commands(commands: dict[str, str]) -> dict[str, str]:
    """Encode a dict of (command, command-output) pairs for env serialization.

    The resulting dict can be passed to the environment of managed instances (via
    subprocess.run() or equivalents).
    """
    if not commands:
        # Empty dict: don't spend time encoding anything.
        return {}

    # The current encoding scheme is to dump the entire dict to base64-encoded json
    # string, then put this resulting string in a dict under the "CRAFT_SECRETS" key.
    as_json = json.dumps(commands)
    as_bytes = as_json.encode("utf-8")
    as_b64 = base64.b64encode(as_bytes)
    as_str = as_b64.decode("ascii")

    return {"CRAFT_SECRETS": as_str}


def _decode_commands(environment: Mapping[str, Any]) -> dict[str, str]:
    as_str = environment.get("CRAFT_SECRETS")

    if as_str is None:
        # Not necessarily an error: it means the project has no secrets.
        return {}

    as_b64 = as_str.encode("ascii")
    as_bytes = base64.b64decode(as_b64)
    as_json = as_bytes.decode("utf-8")

    return cast("dict[str, str]", json.loads(as_json))
