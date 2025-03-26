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

import pydantic
from typing_extensions import Any, Self

from craft_application.models import CraftBaseModel

# Simplified spread configuration


class SpreadBase(CraftBaseModel):
    """Base model for spread.yaml, which can always take and ignore extra items."""

    model_config = pydantic.ConfigDict(
        CraftBaseModel.model_config,  # type: ignore[misc]
        extra="ignore",
    )


class CraftSpreadSystem(SpreadBase):
    """Simplified spread system configuration."""

    workers: int | None = None


class CraftSpreadBackend(SpreadBase):
    """Simplified spread backend configuration."""

    type: str | None = None
    allocate: str | None = None
    discard: str | None = None
    systems: list[dict[str, CraftSpreadSystem | None]]
    prepare: str | None = None
    restore: str | None = None
    prepare_each: str | None = None
    restore_each: str | None = None


class CraftSpreadSuite(SpreadBase):
    """Simplified spread suite configuration."""

    summary: str
    systems: list[str] | None = None
    environment: dict[str, str] | None = None
    prepare: str | None = None
    restore: str | None = None
    prepare_each: str | None = None
    restore_each: str | None = None
    kill_timeout: str | None = None


class CraftSpreadYaml(SpreadBase):
    """Simplified spread project configuration."""

    backends: dict[str, CraftSpreadBackend]
    suites: dict[str, CraftSpreadSuite]
    exclude: list[str] | None = None
    prepare: str | None = None
    restore: str | None = None
    prepare_each: str | None = None
    restore_each: str | None = None
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

    username: str
    password: str
    workers: int | None = None

    @classmethod
    def from_craft(cls, simple: CraftSpreadSystem | None) -> Self:
        """Create a spread system configuration from the simplified version."""
        workers = simple.workers if simple else 1
        return cls(
            workers=workers,
            username="spread",
            password="spread",  # noqa: S106 (possible hardcoded password)
        )


class SpreadBackend(SpreadBaseModel):
    """Processed spread backend configuration."""

    type: str | None = None
    allocate: str | None = None
    discard: str | None = None
    systems: list[dict[str, SpreadSystem]] = pydantic.Field(default_factory=list)
    prepare: str | None = None
    restore: str | None = None
    prepare_each: str | None = None
    restore_each: str | None = None

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
            prepare_each=simple.prepare_each,
            restore_each=simple.restore_each,
        )

    @staticmethod
    def systems_from_craft(
        simple: list[dict[str, CraftSpreadSystem | None]],
    ) -> list[dict[str, SpreadSystem]]:
        """Create spread systems from the simplified version."""
        systems: list[dict[str, SpreadSystem]] = []
        for item in simple:
            entry: dict[str, SpreadSystem] = {}
            for name, ssys in item.items():
                entry[name] = SpreadSystem.from_craft(ssys)
            systems.append(entry)

        return systems


class SpreadSuite(SpreadBaseModel):
    """Processed spread suite configuration."""

    summary: str
    systems: list[str]
    environment: dict[str, str] | None
    prepare: str | None
    restore: str | None
    prepare_each: str | None
    restore_each: str | None
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
    kill_timeout: str | None = None

    @classmethod
    def from_craft(
        cls,
        simple: CraftSpreadYaml,
        *,
        craft_backend: SpreadBackend,
    ) -> Self:
        """Create the spread configuration from the simplified version."""
        return cls(
            project="craft-test",
            environment={
                "SUDO_USER": "",
                "SUDO_UID": "",
                "LANG": "C.UTF-8",
                "LANGUAGE": "en",
                "PROJECT_PATH": "/home/spread/proj",
            },
            backends=cls._backends_from_craft(simple.backends, craft_backend),
            suites=cls._suites_from_craft(simple.suites),
            exclude=simple.exclude or [".git", ".tox"],
            path="/home/spread/proj",
            prepare=simple.prepare,
            restore=simple.restore,
            prepare_each=simple.prepare_each,
            restore_each=simple.restore_each,
            kill_timeout=simple.kill_timeout or None,
        )

    @staticmethod
    def _backends_from_craft(
        simple: dict[str, CraftSpreadBackend], craft_backend: SpreadBackend
    ) -> dict[str, SpreadBackend]:
        backends: dict[str, SpreadBackend] = {}
        for name, backend in simple.items():
            if name == "craft":
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
