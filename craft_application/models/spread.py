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
    def from_craft(cls, csystem: CraftSpreadSystem | None) -> Self:
        """Create a spread system configuration from the simplified version."""
        workers = csystem.workers if csystem else 1
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
    def from_craft(cls, cbackend: CraftSpreadBackend) -> Self:
        """Create a spread backend configuration from the simplified version."""
        return cls(
            type=cbackend.type,
            allocate=cbackend.allocate,
            discard=cbackend.discard,
            systems=cls.systems_from_craft(cbackend.systems),
            prepare=cbackend.prepare,
            restore=cbackend.restore,
            prepare_each=cbackend.prepare_each,
            restore_each=cbackend.restore_each,
        )

    @staticmethod
    def systems_from_craft(
        csystems: list[dict[str, CraftSpreadSystem | None]],
    ) -> list[dict[str, SpreadSystem]]:
        """Create spread systems from the simplified version."""
        systems: list[dict[str, SpreadSystem]] = []
        for item in csystems:
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
    def from_craft(cls, csuite: CraftSpreadSuite) -> Self:
        """Create a spread suite configuration from the simplified version."""
        return cls(
            summary=csuite.summary,
            systems=csuite.systems,
            environment=csuite.environment,
            prepare=csuite.prepare,
            restore=csuite.restore,
            prepare_each=csuite.prepare_each,
            restore_each=csuite.restore_each,
            kill_timeout=csuite.kill_timeout,  # XXX: add time limit
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
        csy: CraftSpreadYaml,
        *,
        craft_backend: SpreadBackend,
        env: dict[str, str],
    ) -> Self:
        """Create the spread configuration from the simplified version."""
        return cls(
            project=csy.project,
            environment={
                "SUDO_USER": "",
                "SUDO_UID": "",
                "LANG": "C.UTF-8",
                "LANGUAGE": "en",
                "PROJECT_PATH": "/home/spread/proj",
                **env,
            },
            backends=cls._backends_from_craft(csy.backends, craft_backend),
            suites=cls._suites_from_craft(csy.suites),
            exclude=csy.exclude or [".git", ".tox"],
            path="/home/spread/proj",
            prepare=csy.prepare,
            restore=csy.restore,
            prepare_each=csy.prepare_each,
            restore_each=csy.restore_each,
            kill_timeout=csy.kill_timeout or "1h",  # XXX: add time limit
            reroot="..",
        )

    @staticmethod
    def _backends_from_craft(
        cbackends: dict[str, CraftSpreadBackend], craft_backend: SpreadBackend
    ) -> dict[str, SpreadBackend]:
        backends: dict[str, SpreadBackend] = {}
        for name, backend in cbackends.items():
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
        csuites: dict[str, CraftSpreadSuite]
    ) -> dict[str, SpreadSuite]:
        return {name: SpreadSuite.from_craft(suite) for name, suite in csuites.items()}
