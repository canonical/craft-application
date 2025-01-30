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
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Models representing spread projects."""


from typing_extensions import Any, Self

from craft_application.models import CraftBaseModel

# Simplified spread configuration


class CraftSpreadSystem(CraftBaseModel):
    """Simplified spread system configuration."""

    workers: int | None = None


class CraftSpreadBackend(CraftBaseModel):
    """Simplified spread backend configuration."""

    type: str
    allocate: str | None = None
    discard: str | None = None
    systems: list[dict[str, CraftSpreadSystem | None]]
    prepare: str | None = None
    restore: str | None = None
    prepare_each: str | None = None
    restore_each: str | None = None


class CraftSpreadSuite(CraftBaseModel):
    """Simplified spread suite configuration."""

    summary: str
    systems: list[str]
    environment: dict[str, str] | None = None
    prepare: str | None = None
    restore: str | None = None
    prepare_each: str | None = None
    restore_each: str | None = None
    kill_timeout: str | None = None


class CraftSpreadYaml(CraftBaseModel):
    """Simplified spread project configuration."""

    project: str
    backends: dict[str, CraftSpreadBackend]
    suites: dict[str, CraftSpreadSuite]
    exclude: list[str] | None = None
    prepare: str | None = None
    restore: str | None = None
    prepare_each: str | None = None
    restore_each: str | None = None
    kill_timeout: str | None = None


# Processed full-form spread configuration


class SpreadBaseModel(CraftBaseModel):
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
    def from_craft(cls, craft_spread_system: CraftSpreadSystem | None) -> Self:
        """Create a spread system configuration from the simplified version."""
        workers = craft_spread_system.workers if craft_spread_system else 1
        return cls(
            workers=workers,
            username="spread",
            password="spread",  # noqa: S106 (possible hardcoded password)
        )


class SpreadBackend(SpreadBaseModel):
    """Processed spread backend configuration."""

    type: str
    allocate: str | None = None
    discard: str | None = None
    systems: list[dict[str, SpreadSystem]] = []
    prepare: str | None = None
    restore: str | None = None
    prepare_each: str | None = None
    restore_each: str | None = None

    @classmethod
    def from_craft(cls, craft_spread_backend: CraftSpreadBackend) -> Self:
        """Create a spread backend configuration from the simplified version."""
        return cls(
            type=craft_spread_backend.type,
            allocate=craft_spread_backend.allocate,
            discard=craft_spread_backend.discard,
            systems=cls.systems_from_craft(craft_spread_backend.systems),
            prepare=craft_spread_backend.prepare,
            restore=craft_spread_backend.restore,
            prepare_each=craft_spread_backend.prepare_each,
            restore_each=craft_spread_backend.restore_each,
        )

    @staticmethod
    def systems_from_craft(
        craft_spread_systems: list[dict[str, CraftSpreadSystem | None]],
    ) -> list[dict[str, SpreadSystem]]:
        """Create spread systems from the simplified version."""
        systems: list[dict[str, SpreadSystem]] = []
        for item in craft_spread_systems:
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
    def from_craft(cls, craft_spread_suite: CraftSpreadSuite) -> Self:
        """Create a spread suite configuration from the simplified version."""
        return cls(
            summary=craft_spread_suite.summary,
            systems=craft_spread_suite.systems,
            environment=craft_spread_suite.environment,
            prepare=craft_spread_suite.prepare,
            restore=craft_spread_suite.restore,
            prepare_each=craft_spread_suite.prepare_each,
            restore_each=craft_spread_suite.restore_each,
            kill_timeout=craft_spread_suite.kill_timeout,  # XXX: add time limit
        )


class SpreadYaml(SpreadBaseModel):
    """Processed spread project configuration."""

    project: str
    environment: dict[str, str]
    backends: dict[str, SpreadBackend]
    suites: dict[str, SpreadSuite]
    exclude: list[str]
    path: str
    reroot: str | None
    prepare: str | None
    restore: str | None
    prepare_each: str | None
    restore_each: str | None
    kill_timeout: str

    @classmethod
    def from_craft(
        cls,
        craft_spread_yaml: CraftSpreadYaml,
        *,
        craft_backend: SpreadBackend,
        env: dict[str, str],
    ) -> Self:
        """Create the spread configuration from the simplified version."""
        return cls(
            project=craft_spread_yaml.project,
            environment={
                "SUDO_USER": "",
                "SUDO_UID": "",
                "LANG": "C.UTF-8",
                "LANGUAGE": "en",
                "PROJECT_PATH": "/home/spread/proj",
                **env,
            },
            backends=cls._backends_from_craft(craft_spread_yaml.backends, craft_backend),
            suites=cls._suites_from_craft(craft_spread_yaml.suites),
            exclude=craft_spread_yaml.exclude or [".git", ".tox"],
            path="/home/spread/proj",
            prepare=craft_spread_yaml.prepare,
            restore=craft_spread_yaml.restore,
            prepare_each=craft_spread_yaml.prepare_each,
            restore_each=craft_spread_yaml.restore_each,
            kill_timeout=craft_spread_yaml.kill_timeout or "1h",  # XXX: add time limit
            reroot="..",
        )

    @staticmethod
    def _backends_from_craft(
        craft_spread_backends: dict[str, CraftSpreadBackend], craft_backend: SpreadBackend
    ) -> dict[str, SpreadBackend]:
        backends: dict[str, SpreadBackend] = {}
        for name, backend in craft_spread_backends.items():
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
        craft_spread_suites: dict[str, CraftSpreadSuite]
    ) -> dict[str, SpreadSuite]:
        return {name: SpreadSuite.from_craft(suite) for name, suite in craft_spread_suites.items()}
