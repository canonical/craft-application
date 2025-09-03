# This file is part of craft-application.
#
# Copyright 2024-2025 Canonical Ltd.
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
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Models representing spread projects."""

import pathlib
import re

import pydantic
from typing_extensions import Any, Self

from craft_application.models import CraftBaseModel

# Simplified spread configuration


class SpreadBase(CraftBaseModel):
    """Base model for spread.yaml, which can always take and ignore extra items."""

    model_config = pydantic.ConfigDict(
        CraftBaseModel.model_config,  # type: ignore[misc]
        extra="allow",
    )


class CraftSpreadSystem(SpreadBase):
    """Simplified spread system configuration."""

    workers: int | None = None


class CraftSpreadBackend(SpreadBase):
    """Simplified spread backend configuration."""

    type: str | None = None
    allocate: str | None = None
    discard: str | None = None
    systems: list[str | dict[str, CraftSpreadSystem | None]]
    prepare: str | None = None
    restore: str | None = None
    debug: str | None = None
    prepare_each: str | None = None
    restore_each: str | None = None
    debug_each: str | None = None


class CraftSpreadSuite(SpreadBase):
    """Simplified spread suite configuration."""

    summary: str
    systems: list[str] | None = None
    environment: dict[str, str] | None = None
    prepare: str | None = None
    restore: str | None = None
    debug: str | None = None
    prepare_each: str | None = None
    restore_each: str | None = None
    debug_each: str | None = None
    kill_timeout: str | None = None


class CraftSpreadYaml(SpreadBase):
    """Simplified spread project configuration."""

    model_config = pydantic.ConfigDict(
        SpreadBase.model_config,  # type: ignore[misc]
        extra="forbid",
    )

    project: str | None = None
    backends: dict[str, CraftSpreadBackend]
    suites: dict[str, CraftSpreadSuite]
    exclude: list[str] | None = None
    prepare: str | None = None
    restore: str | None = None
    debug: str | None = None
    prepare_each: str | None = None
    restore_each: str | None = None
    debug_each: str | None = None
    kill_timeout: str | None = None


# Processed full-form spread configuration


class SpreadBaseModel(SpreadBase):
    """Base for spread models."""

    def model_post_init(self, /, __context: Any) -> None:  # noqa: ANN401
        """Remove attributes set to None."""
        none_items: list[Any] = []
        for k, v in self.__dict__.items():
            if v is None:
                none_items.append(k)

        for k in none_items:
            k.replace("_", "-")
            delattr(self, k)


class SpreadSystem(SpreadBaseModel):
    """Processed spread system configuration."""

    username: str | None = None
    password: str | None = None
    workers: int | None = None

    @classmethod
    def from_craft(cls, simple: CraftSpreadSystem | None) -> Self:
        """Create a spread system configuration from the simplified version."""
        workers = simple.workers if simple else 1
        return cls(workers=workers)


class SpreadBackend(SpreadBaseModel):
    """Processed spread backend configuration."""

    type: str | None = None
    allocate: str | None = None
    discard: str | None = None
    systems: list[str | dict[str, SpreadSystem]] = pydantic.Field(
        default_factory=list[str | dict[str, SpreadSystem]]
    )
    prepare: str | None = None
    restore: str | None = None
    debug: str | None = None
    prepare_each: str | None = None
    restore_each: str | None = None
    debug_each: str | None = None

    @classmethod
    def from_craft(cls, simple: CraftSpreadBackend) -> Self:
        """Create a spread backend configuration from the simplified version."""
        return cls(
            type=simple.type,
            allocate=simple.allocate,
            discard=simple.discard,
            systems=cls.systems_from_craft(simple.systems),
            prepare=simple.prepare,
            restore=simple.restore,
            debug=simple.debug,
            prepare_each=simple.prepare_each,
            restore_each=simple.restore_each,
            debug_each=simple.debug_each,
        )

    @staticmethod
    def systems_from_craft(
        simple: list[str | dict[str, CraftSpreadSystem | None]],
    ) -> list[str | dict[str, SpreadSystem]]:
        """Create spread systems from the simplified version."""
        systems: list[str | dict[str, SpreadSystem]] = []
        for item in simple:
            if isinstance(item, str):
                systems.append(item)
                continue
            entry: dict[str, SpreadSystem] = {}
            for name, ssys in item.items():
                entry[name] = SpreadSystem.from_craft(ssys)
            systems.append(entry)

        return systems


class SpreadSuite(SpreadBaseModel):
    """Processed spread suite configuration."""

    summary: str
    systems: list[str] | None
    environment: dict[str, str] | None
    prepare: str | None
    restore: str | None
    prepare_each: str | None
    restore_each: str | None
    debug: str | None = None
    debug_each: str | None = None
    kill_timeout: str | None = None

    @classmethod
    def from_craft(cls, simple: CraftSpreadSuite) -> Self:
        """Create a spread suite configuration from the simplified version."""
        return cls(
            summary=simple.summary,
            systems=simple.systems or [],
            environment=simple.environment,
            prepare=simple.prepare,
            restore=simple.restore,
            prepare_each=simple.prepare_each,
            restore_each=simple.restore_each,
            kill_timeout=simple.kill_timeout,
            debug=simple.debug,
            debug_each=simple.debug_each,
        )


class SpreadYaml(SpreadBaseModel):
    """Processed spread project configuration."""

    project: str
    environment: dict[str, str]
    backends: dict[str, SpreadBackend]
    suites: dict[str, SpreadSuite]
    exclude: list[str]
    path: str
    prepare: str | None
    restore: str | None
    prepare_each: str | None
    restore_each: str | None
    debug: str | None = None
    debug_each: str | None = None
    kill_timeout: str | None = None
    reroot: str | None = None

    @classmethod
    def from_craft(
        cls,
        simple: CraftSpreadYaml,
        *,
        craft_backend: SpreadBackend,
        artifact: pathlib.Path,
        resources: dict[str, pathlib.Path],
    ) -> Self:
        """Create the spread configuration from the simplified version."""
        environment = {
            "SUDO_USER": "",
            "SUDO_UID": "",
            "LANG": "C.UTF-8",
            "LANGUAGE": "en",
            "PROJECT_PATH": "/root/proj",
            "CRAFT_ARTIFACT": f"$PROJECT_PATH/{artifact}",
        }

        for name, path in resources.items():
            var_name = cls._translate_resource_name(name)
            environment[f"CRAFT_RESOURCE_{var_name}"] = f"$PROJECT_PATH/{path}"

        return cls(
            project="craft-test",
            environment=environment,
            backends=cls._backends_from_craft(simple.backends, craft_backend),
            suites=cls._suites_from_craft(simple.suites),
            exclude=simple.exclude or [".git", ".tox"],
            path="/root/proj",
            prepare=simple.prepare,
            restore=simple.restore,
            prepare_each=simple.prepare_each,
            restore_each=simple.restore_each,
            kill_timeout=simple.kill_timeout or None,
            debug=simple.debug,
            debug_each=simple.debug_each,
            reroot="..",
        )

    @staticmethod
    def _translate_resource_name(name: str) -> str:
        return re.sub(r"[^A-Za-z0-9_]", "_", name).upper()

    @staticmethod
    def _backends_from_craft(
        simple: dict[str, CraftSpreadBackend], craft_backend: SpreadBackend
    ) -> dict[str, SpreadBackend]:
        backends: dict[str, SpreadBackend] = {}
        for name, backend in simple.items():
            # Spread assumes the backend name as the type when it's not explicitly declared.
            if name == "craft" and (not backend.type or backend.type == "craft"):
                craft_backend.systems = SpreadBackend.systems_from_craft(
                    backend.systems
                )
                backends[name] = craft_backend
            else:
                backends[name] = SpreadBackend.from_craft(backend)

        return backends

    @staticmethod
    def _suites_from_craft(
        simple: dict[str, CraftSpreadSuite],
    ) -> dict[str, SpreadSuite]:
        return {name: SpreadSuite.from_craft(suite) for name, suite in simple.items()}
