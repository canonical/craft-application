#  This file is part of craft-application.
#
#  Copyright 2024 Canonical Ltd.
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
"""Service class for managing secrets."""

from __future__ import annotations

import base64
import json
import os
import re
import subprocess
from collections.abc import Iterable, Mapping, Sequence
from typing import TYPE_CHECKING, Any, final

import craft_cli

from craft_application import errors

from . import base

if TYPE_CHECKING:
    from craft_application.application import AppMetadata
    from craft_application.services.service_factory import ServiceFactory

_SECRET_REGEX = re.compile(r"\$\(HOST_SECRET:(?P<command>.*)\)")


@final
class SecretsService(base.AppService):
    """A service for managing secrets."""

    def __init__(self, app: AppMetadata, services: ServiceFactory) -> None:
        super().__init__(app, services)
        self.__secrets: dict[str, str] = {}

    def setup(self) -> None:
        super().setup()
        if self._services.provider.is_managed():
            self.__secrets = _load_from_environment()
        else:
            self.__secrets = {}
        craft_cli.emit.set_secrets(list(self.__secrets.values()))

    def __setitem__(self, key: str, value: str) -> None:
        self.__secrets[key] = value
        craft_cli.emit.set_secrets(list(self.__secrets.values()))

    def __serialize(self) -> str:
        """Convert the current set of secrets to a base64-encoded JSON string."""
        jsonified = json.dumps(self.__secrets)
        return base64.b64encode(jsonified.encode("utf-8")).decode("ascii")

    def __render_secret(self, original: str) -> str:
        if not (match := _SECRET_REGEX.search(original)):
            return original
        command = match.group("command")
        host_directive = match.group(0)

        if not (output := self.__secrets.get(command)):
            if self._services.provider.is_managed():
                # In managed mode the command *must* be in the cache; this is an error.
                raise errors.SecretsManagedError(host_directive)

            try:
                output = _run_command(command)
            except subprocess.CalledProcessError as err:
                raise errors.SecretsCommandError(
                    host_directive, err.stderr.decode()
                ) from err
            self[command] = output

        return original.replace(host_directive, output)

    def __render_part(self, part: dict[str, Any]) -> None:
        """Render secrets in the given part dict, mutating the dict itself."""
        # Render "source"
        if "source" in part:
            part["source"] = self.__render_secret(part["source"])

        # Render "build-environment"
        if "build-environment" in part:
            for single_entry_dict in part["build-environment"]:
                for var_name, var_value in single_entry_dict.items():
                    single_entry_dict[var_name] = self.__render_secret(var_value)

    def __check_no_secrets(self, data: object) -> None:
        """Check that the given data structure does not contain any unrendered secrets.

        :raises: SecretsInFieldsError if any secret directives remain in the structure.
        """
        secrets_fields = _find_secrets(data)
        if secrets_fields:
            raise errors.SecretsInFieldsError(secrets_fields)

    def render(self, /, data: dict[str, Any]) -> Mapping[str, str]:
        """Render the build secrets for a given data structure.

        This function will process directives of the form $(HOST_SECRET:<cmd>) in
        string values in ``yaml_data``. For each such directive, the <cmd> part is
        executed (with bash) and the resulting output replaces the whole directive.
        The returned object contains the result of HOST_SECRET processing (for masking
        with craft-cli and forwarding to managed instances).

        Note that only a few fields are currently supported:

        - "source" and "build-environment" for parts.

        Using HOST_SECRET directives in any other field is an error.

        :param data: The project's loaded data
        :returns: a BuildSecrets object containing the environment dictionary and the
            actual secret text.
        """
        # Process the fields where we allow build secrets
        parts = data.get("parts", {})
        for part in parts.values():
            self.__render_part(part)

        self.__check_no_secrets(data)

        return data

    def get_environment(self) -> dict[str, str]:
        """Get the environment to pass to an inner process based on these secrets."""
        value = self.__serialize()
        craft_cli.emit.set_secrets([value, *self.__secrets.values()])
        return {"CRAFT_SECRETS": value}


def _find_secrets(data: Any) -> dict[Sequence[str | int], str]:  # noqa: ANN401
    """Find the paths of all secrets in the given data structure."""
    secrets: dict[Sequence[str | int], str] = {}

    if isinstance(data, str):
        match = _SECRET_REGEX.search(data)
        if match:
            secrets[()] = match.group()
    elif isinstance(data, Mapping):
        for key, value in data.items():  # type: ignore[reportUnknownVariableType]
            child_secrets = _find_secrets(value)
            for path, secret in child_secrets.items():
                secrets[(key, *path)] = secret
    elif isinstance(data, Sequence):
        for idx, item in enumerate(data):  # type: ignore[reportUnknownVariableType]
            child_secrets = _find_secrets(item)
            for path, secret in child_secrets.items():
                secrets[(idx, *path)] = secret
    elif isinstance(data, Iterable):
        for item in data:  # type: ignore[reportUnknownVariableType]
            secrets.update(_find_secrets(item))

    return secrets


def _load_from_environment() -> dict[str, str]:
    """Load secrets from an environment variable."""
    raw = os.getenv("CRAFT_SECRETS")
    if not raw:
        return {}

    json_bytes = base64.b64decode(raw)
    return json.loads(json_bytes.decode("utf-8"))


def _run_command(command: str) -> str:
    bash_command = f"set -euo pipefail; {command}"
    return (
        subprocess.check_output(["bash", "-c", bash_command], stderr=subprocess.PIPE)
        .decode("utf-8")
        .strip()
    )
