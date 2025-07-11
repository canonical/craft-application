# This file is part of craft-application.
#
# Copyright 2023-2025 Canonical Ltd.
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

import dataclasses
from typing import Annotated, Any

import craft_parts
import craft_providers.bases
import pydantic
from craft_cli import emit
from craft_providers.errors import BaseConfigurationError

from craft_application.models import base
from craft_application.models.constraints import (
    ProjectName,
    ProjectTitle,
    SummaryStr,
    UniqueStrList,
    VersionStr,
)
from craft_application.models.platforms import (
    Platform,
    PlatformsDict,
)


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
        # current_devel_base should point to 25.04, which is not available yet
        current_devel_base=craft_providers.bases.ubuntu.BuilddBaseAlias.DEVEL,
        devel_base=craft_providers.bases.ubuntu.BuilddBaseAlias.DEVEL,
    ),
]

DEVEL_BASE_WARNING = (
    "The development build-base should only be used for testing purposes, "
    "as its contents are bound to change with the opening of new Ubuntu releases, "
    "suddenly and without warning."
)


def _expand_shorthand_platforms(platforms: dict[str, Any]) -> dict[str, Any]:
    """Expand shorthand platform entries into standard form.

    Assumes the platform label is a valid as a build-on and build-for entry.

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


def _validate_package_repository(repository: dict[str, Any]) -> dict[str, Any]:
    """Validate a package repository with lazy loading of craft-archives.

    :param repository: a dictionary representing a package repository.
    :returns: That same dictionary, if valid.
    :raises: ValueError if the repository is not valid.
    """
    # This check is not always used, import it here to avoid unnecessary
    from craft_archives import repo  # type: ignore[import-untyped]  # noqa: PLC0415

    repo.validate_repository(repository)
    return repository


def _validate_part(part: dict[str, Any]) -> dict[str, Any]:
    """Verify each part (craft-parts will re-validate this)."""
    craft_parts.validate_part(part)
    return part


Part = Annotated[dict[str, Any], pydantic.BeforeValidator(_validate_part)]


class Project(base.CraftBaseModel):
    """Craft Application project definition."""

    name: ProjectName
    title: ProjectTitle | None = None
    version: VersionStr | None = None
    summary: SummaryStr | None = None
    description: str | None = None

    base: str | None = None
    build_base: str | None = None
    platforms: PlatformsDict

    contact: str | UniqueStrList | None = None
    issues: str | UniqueStrList | None = None
    source_code: pydantic.AnyUrl | None = None
    license: str | None = None

    adopt_info: str | None = None

    # parts are handled by craft-parts
    parts: dict[str, Part]

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
        """Expand shorthand platform entries into standard form."""
        return _expand_shorthand_platforms(platforms)

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
