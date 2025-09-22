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
import textwrap
from typing import Annotated, Any

import craft_parts
import craft_providers.bases
import pydantic
from craft_cli import emit
from craft_providers.errors import BaseConfigurationError
from typing_extensions import Self

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
        current_devel_base=craft_providers.bases.ubuntu.BuilddBaseAlias.QUESTING,
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
    """The class that defines the project model."""

    name: ProjectName
    title: ProjectTitle | None = None
    version: VersionStr | None = None
    summary: SummaryStr | None = None

    description: str | None = pydantic.Field(
        default=None,
        description="The full description of the project.",
    )
    """The full description of the project.

    This is a free-form field, but it is typically assigned one to two brief paragraphs
    describing what the project does and who may find it useful.
    """

    base: str | None = None
    build_base: str | None = None

    platforms: PlatformsDict = pydantic.Field(
        description="Determines which architectures the project builds and runs on.",
        examples=[
            "{amd64: {build-on: [amd64], build-for: [amd64]}, arm64: {build-on: [amd64, arm64], build-for: [arm64]}}"
        ],
    )
    """Determines which architectures the project builds and runs on.

    If the platform name is a valid Debian architecture, the ``build-on`` and
    ``build-for`` keys can be omitted.

    The platform name describes a ``build-on``-``build-for`` pairing.  When setting
    ``build-on`` and ``build-for``, the name is arbitrary but it's recommended to match
    the platform name to the architecture set by ``build-for``.
    """

    contact: str | UniqueStrList | None = pydantic.Field(
        default=None,
        description="The author's contact links and email addresses.",
        examples=["[contact@example.com, https://example.com/contact]"],
    )

    issues: str | UniqueStrList | None = pydantic.Field(
        default=None,
        description="The links and email addresses for submitting issues, bugs, and feature requests.",
        examples=["[issues@example.com, https://example.com/issues]"],
    )

    source_code: pydantic.AnyUrl | None = pydantic.Field(
        default=None,
        description="The links to the source code of the project.",
        examples=["[https://github.com/canonical/craft-application]"],
    )

    license: str | None = pydantic.Field(
        default=None,
        description="The project's license as an SPDX expression",
        examples=["GPL-3.0+", "Apache-2.0"],
    )
    """The project's license as an SPDX expression.

    Currently, only `SPDX 2.1 expressions <https://spdx.org/licenses/>`_ are supported.

    For “or later” and “with exception” license styles, refer to `Appendix V of the SPDX
    Specification 2.1
    <https://web.archive.org/web/20230902152422/https://spdx.dev/spdx-specification-21-web-version/#h.twlc0ztnng3b>`_.
    """

    adopt_info: str | None = pydantic.Field(
        default=None,
        description="Selects a part to inherit metadata from.",
        examples=["foo-part"],
    )

    # parts are handled by craft-parts
    parts: dict[str, Part] = pydantic.Field(
        description="The self-contained software pieces needed to create the final artifact.",
        examples=[
            textwrap.dedent(
                "{cloud-init: \
                {plugin: python, \
                source-type: git, \
                source: https://git.launchpad.net/cloud-init}}"
            ),
        ],
    )
    """The self-contained software pieces needed to create the final artifact.

    A part's behavior is driven by its plugin. Custom behavior can be defined with the
    ``override-`` keys.
    """

    package_repositories: (
        list[
            Annotated[
                dict[str, Any], pydantic.AfterValidator(_validate_package_repository)
            ]
        ]
        | None
    ) = pydantic.Field(
        default=None,
        description="The package repositories to use for build and stage packages.",
        examples=[
            textwrap.dedent(
                "[{type: apt,\
                components: [main],\
                suites: [xenial],\
                key-id: 78E1918602959B9C59103100F1831DDAFC42E99D,\
                url: http://ppa.launchpad.net/snappy-dev/snapcraft-daily/ubuntu}]",
            ),
        ],
    )
    """The APT package repositories to use as sources for build and stage packages.

    The Debian, Personal Package Archive (PPA), and Ubuntu Cloud Archive (UCA) package
    formats are supported.
    """

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
        # if there is no base or it's bare, do not validate the build-base
        if not base or base == "bare":
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

    @pydantic.model_validator(mode="after")
    def _validate_bare_base_requires_build_base(self) -> Self:
        """Validate that a build-base must be provided if base is bare."""
        if self.base != "bare":
            return self

        if not self.build_base:
            raise ValueError(f"A build-base is required if base is {self.base!r}")

        return self
