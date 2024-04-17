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
from typing import Any

import craft_parts
import craft_providers.bases
import pydantic
from pydantic import AnyUrl
from typing_extensions import override

from craft_application import errors
from craft_application.models.base import CraftBaseConfig, CraftBaseModel
from craft_application.models.constraints import (
    MESSAGE_INVALID_NAME,
    MESSAGE_INVALID_VERSION,
    ProjectName,
    ProjectTitle,
    SummaryStr,
    UniqueStrList,
    VersionStr,
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
        # TODO: current_devel_base should point to 24.10, which is not available yet
        current_devel_base=craft_providers.bases.ubuntu.BuilddBaseAlias.DEVEL,
        devel_base=craft_providers.bases.ubuntu.BuilddBaseAlias.DEVEL,
    ),
]


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


class BuildPlannerConfig(CraftBaseConfig):
    """Config for BuildProjects."""

    extra = pydantic.Extra.ignore
    """The BuildPlanner model uses attributes from the project yaml."""


class BuildPlanner(CraftBaseModel, metaclass=abc.ABCMeta):
    """The BuildPlanner obtains a build plan for the project."""

    Config = BuildPlannerConfig

    @abc.abstractmethod
    def get_build_plan(self) -> list[BuildInfo]:
        """Obtain the list of architectures and bases from the project file."""


class Project(CraftBaseModel):
    """Craft Application project definition."""

    name: ProjectName
    title: ProjectTitle | None
    version: VersionStr | None
    summary: SummaryStr | None
    description: str | None

    base: Any | None = None
    build_base: Any | None = None
    platforms: dict[str, Any] | None = None

    contact: str | UniqueStrList | None
    issues: str | UniqueStrList | None
    source_code: AnyUrl | None
    license: str | None

    adopt_info: str | None

    parts: dict[str, dict[str, Any]]  # parts are handled by craft-parts

    package_repositories: list[dict[str, Any]] | None

    @pydantic.validator(  # pyright: ignore[reportUnknownMemberType,reportUntypedFunctionDecorator]
        "parts", each_item=True
    )
    def _validate_parts(cls, item: dict[str, Any]) -> dict[str, Any]:
        """Verify each part (craft-parts will re-validate this)."""
        craft_parts.validate_part(item)
        return item

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
    @abc.abstractmethod
    def _providers_base(cls, base: str) -> craft_providers.bases.BaseAlias | None:
        """Get a BaseAlias from the application's base.

        :param base: The application-specific base name.

        :returns: The BaseAlias for the base or None if the base does not map to
          a BaseAlias.

        :raises CraftValidationError: If the project's base cannot be determined.
        """

    @pydantic.root_validator(  # pyright: ignore[reportUnknownMemberType,reportUntypedFunctionDecorator]
        pre=False
    )
    def _validate_devel(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Validate the build-base is 'devel' for the current devel base."""
        base = values.get("base")
        # if there is no base, do not validate the build-base
        if not base:
            return values

        base_alias = cls._providers_base(base)

        # if the base does not map to a base alias, do not validate the build-base
        if not base_alias:
            return values

        build_base = values.get("build_base") or base
        build_base_alias = cls._providers_base(build_base)

        for devel_base_info in DEVEL_BASE_INFOS:
            if (
                base_alias == devel_base_info.current_devel_base
                and build_base_alias != devel_base_info.devel_base
            ):
                raise errors.CraftValidationError(
                    f"build-base must be 'devel' when base is {base!r}"
                )

        return values

    @override
    @classmethod
    def transform_pydantic_error(cls, error: pydantic.ValidationError) -> None:
        errors_to_messages: dict[tuple[str, str], str] = {
            ("version", "value_error.str.regex"): MESSAGE_INVALID_VERSION,
            ("name", "value_error.str.regex"): MESSAGE_INVALID_NAME,
        }

        CraftBaseModel.transform_pydantic_error(error)

        for error_dict in error.errors():
            loc_and_type = (str(error_dict["loc"][0]), error_dict["type"])
            if message := errors_to_messages.get(loc_and_type):
                # Note that unfortunately, Pydantic 1.x does not have the
                # "input" key in the error dict, so we can't put the original
                # value in the error message.
                error_dict["msg"] = message

    @pydantic.validator(  # pyright: ignore[reportUnknownMemberType,reportUntypedFunctionDecorator]
        "package_repositories", each_item=True
    )
    def _validate_package_repositories(
        cls, repository: dict[str, Any]
    ) -> dict[str, Any]:
        # This check is not always used, import it here to avoid unnecessary
        from craft_archives import repo  # type: ignore[import-untyped]

        repo.validate_repository(repository)

        return repository
