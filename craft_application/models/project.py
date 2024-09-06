# This file is part of craft-application.
#
# Copyright 2023-2024 Canonical Ltd.
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
"""Basic project model for a craft-application.

This defines the structure of the input file (e.g. snapcraft.yaml)
"""
import abc
import dataclasses
from collections.abc import Mapping
from typing import Annotated, Any

import craft_parts
import craft_providers.bases
import pydantic
from craft_cli import emit
from craft_providers import bases
from craft_providers.errors import BaseConfigurationError

from craft_application import errors
from craft_application.models import base
from craft_application.models.constraints import (
    ProjectName,
    ProjectTitle,
    SingleEntryList,
    SummaryStr,
    UniqueList,
    UniqueStrList,
    VersionStr,
)
from craft_application.util import is_valid_architecture


@dataclasses.dataclass
class DevelBaseInfo:
    """Devel base information for an OS."""

    current_devel_base: craft_providers.bases.BaseAlias
    """The base that the 'devel' alias currently points to."""

    devel_base: craft_providers.bases.BaseAlias
    """The devel base."""


# A list of DevelBaseInfo objects that define an OS's current devel base and devel base.
DEVEL_BASE_INFOS = [
    DevelBaseInfo(
        # TODO: current_devel_base should point to 24.10, which is not available yet
        current_devel_base=craft_providers.bases.ubuntu.BuilddBaseAlias.DEVEL,
        devel_base=craft_providers.bases.ubuntu.BuilddBaseAlias.DEVEL,
    ),
]

DEVEL_BASE_WARNING = (
    "The development build-base should only be used for testing purposes, "
    "as its contents are bound to change with the opening of new Ubuntu releases, "
    "suddenly and without warning."
)


@dataclasses.dataclass
class BuildInfo:
    """Platform build information."""

    platform: str
    """The platform name."""

    build_on: str
    """The architecture to build on."""

    build_for: str
    """The architecture to build for."""

    base: craft_providers.bases.BaseName
    """The base to build on."""


class Platform(base.CraftBaseModel):
    """Project platform definition."""

    build_on: UniqueList[str] | None = pydantic.Field(min_length=1)
    build_for: SingleEntryList[str] | None = None

    @pydantic.field_validator("build_on", "build_for", mode="before")
    @classmethod
    def _vectorise_architectures(cls, values: str | list[str]) -> list[str]:
        """Convert string build-on and build-for to lists."""
        if isinstance(values, str):
            return [values]
        return values

    @pydantic.field_validator("build_on", "build_for", mode="after")
    @classmethod
    def _validate_architectures(cls, values: list[str]) -> list[str]:
        """Validate the architecture entries."""
        for architecture in values:
            if architecture != "all" and not is_valid_architecture(architecture):
                raise errors.CraftValidationError(
                    f"Invalid architecture: {architecture!r} "
                    "must be a valid debian architecture."
                )

        return values

    @pydantic.model_validator(mode="before")
    @classmethod
    def _validate_platform_set(
        cls, values: Mapping[str, list[str]]
    ) -> Mapping[str, Any]:
        """If build_for is provided, then build_on must also be."""
        if values.get("build_for") and not values.get("build_on"):
            raise errors.CraftValidationError(
                "'build-for' expects 'build-on' to also be provided."
            )

        return values


def _populate_platforms(platforms: dict[str, Any]) -> dict[str, Any]:
    """Populate empty platform entries.

    :param platforms: The platform data.

    :returns: The dict of platforms with populated entries.
    """
    for platform_label, platform in platforms.items():
        if not platform:
            # populate "empty" platforms entries from the platform's name
            platforms[platform_label] = {
                "build-on": [platform_label],
                "build-for": [platform_label],
            }

    return platforms


class BuildPlanner(base.CraftBaseModel, metaclass=abc.ABCMeta):
    """The BuildPlanner obtains a build plan for the project."""

    model_config = pydantic.ConfigDict(
        validate_assignment=True,
        extra="ignore",
        populate_by_name=True,
        alias_generator=base.alias_generator,
    )

    platforms: dict[str, Platform]
    base: str | None = None
    build_base: str | None = None

    @pydantic.field_validator("platforms", mode="before")
    @classmethod
    def _populate_platforms(cls, platforms: dict[str, Any]) -> dict[str, Any]:
        """Populate empty platform entries."""
        return _populate_platforms(platforms)

    @pydantic.field_validator("platforms", mode="after")
    @classmethod
    def _validate_platforms_all_keyword(
        cls, platforms: dict[str, Any]
    ) -> dict[str, Any]:
        """Validate `all` keyword is properly used.

        Validation rules:
        - `all` cannot be used to `build-on`
        - If `all` is used for `build-for`, no other architectures can be defined
          for `build-for`.

        :raises ValueError: if `all` keyword isn't properly used.
        """
        # track if 'all' is used in any platform
        is_all_used = False

        # validate `all` inside each platform:
        for platform in platforms.values():
            if platform.build_on and "all" in platform.build_on:
                raise ValueError("'all' cannot be used for 'build-on'")
            if platform.build_for and "all" in platform.build_for:
                is_all_used = True

        # validate `all` across all platforms:
        if len(platforms) > 1 and is_all_used:
            raise ValueError(
                "one of the platforms has 'all' in 'build-for', but there are"
                f" {len(platforms)} platforms: upon release they will conflict."
                "'all' should only be used if there is a single item"
            )

        return platforms

    @property
    def effective_base(self) -> bases.BaseName:
        """Get the Base name for craft-providers."""
        base = self.build_base if self.build_base else self.base

        if not base:
            raise errors.CraftValidationError("Could not determine effective base")

        name, _, channel = base.partition("@")

        return bases.BaseName(name, channel)

    def get_build_plan(self) -> list[BuildInfo]:
        """Obtain the list of architectures and bases from the Project."""
        build_infos: list[BuildInfo] = []

        for platform_label, platform in self.platforms.items():
            for build_for in platform.build_for or [platform_label]:
                for build_on in platform.build_on or [platform_label]:
                    build_infos.append(
                        BuildInfo(
                            platform=platform_label,
                            build_on=build_on,
                            build_for=build_for,
                            base=self.effective_base,
                        )
                    )

        return build_infos


def _validate_package_repository(repository: dict[str, Any]) -> dict[str, Any]:
    """Validate a package repository with lazy loading of craft-archives.

    :param repository: a dictionary representing a package repository.
    :returns: That same dictionary, if valid.
    :raises: ValueError if the repository is not valid.
    """
    # This check is not always used, import it here to avoid unnecessary
    from craft_archives import repo  # type: ignore[import-untyped]

    repo.validate_repository(repository)
    return repository


def _validate_part(part: dict[str, Any]) -> dict[str, Any]:
    """Verify each part (craft-parts will re-validate this)."""
    craft_parts.validate_part(part)
    return part


class Project(base.CraftBaseModel):
    """Craft Application project definition."""

    name: ProjectName
    title: ProjectTitle | None = None
    version: VersionStr | None = None
    summary: SummaryStr | None = None
    description: str | None = None

    base: str | None = None
    build_base: str | None = None
    platforms: dict[str, Platform]

    contact: str | UniqueStrList | None = None
    issues: str | UniqueStrList | None = None
    source_code: pydantic.AnyUrl | None = None
    license: str | None = None

    adopt_info: str | None = None

    parts: dict[  # parts are handled by craft-parts
        str,
        Annotated[dict[str, Any], pydantic.BeforeValidator(_validate_part)],
    ]

    package_repositories: (
        list[
            Annotated[
                dict[str, Any], pydantic.AfterValidator(_validate_package_repository)
            ]
        ]
        | None
    ) = None

    @pydantic.field_validator("platforms", mode="before")
    @classmethod
    def _populate_platforms(cls, platforms: dict[str, Platform]) -> dict[str, Platform]:
        """Populate empty platform entries."""
        return _populate_platforms(platforms)

    @property
    def effective_base(self) -> Any:  # noqa: ANN401 app specific classes can improve
        """Return the base used for creating the output."""
        build_base = getattr(self, "build_base", None)
        if build_base is not None:
            return build_base
        if self.base is not None:
            return self.base
        raise RuntimeError("Could not determine effective base")

    @classmethod
    def _providers_base(cls, base: str) -> craft_providers.bases.BaseAlias | None:
        """Get a BaseAlias from the Project base.

        The default naming convention for a base is 'name@channel'. This method
        should be overridden for applications with a different naming convention.

        :param base: The base name.

        :returns: The BaseAlias for the base or None if the base does not map to
          a BaseAlias.

        :raises CraftValidationError: If the project's base cannot be determined.
        """
        try:
            name, channel = base.split("@")
            return craft_providers.bases.get_base_alias(
                craft_providers.bases.BaseName(name, channel)
            )
        except (ValueError, BaseConfigurationError) as err:
            raise ValueError(f"Unknown base {base!r}") from err

    @pydantic.field_validator("build_base", mode="before")
    @classmethod
    def _validate_devel_base(
        cls, build_base: str, info: pydantic.ValidationInfo
    ) -> str:
        """Validate the build-base is 'devel' for the current devel base."""
        base = info.data.get("base")
        # if there is no base, do not validate the build-base
        if not base:
            return build_base

        base_alias = cls._providers_base(base)

        # if the base does not map to a base alias, do not validate the build-base
        if not base_alias:
            return build_base

        build_base_alias = cls._providers_base(build_base or base)

        # warn if a devel build-base is being used, error if a devel build-base is not
        # used for a devel base
        for devel_base_info in DEVEL_BASE_INFOS:
            if base_alias == devel_base_info.current_devel_base:
                if build_base_alias == devel_base_info.devel_base:
                    emit.message(DEVEL_BASE_WARNING)
                else:
                    raise ValueError(
                        f"A development build-base must be used when base is {base!r}"
                    )

        return build_base
