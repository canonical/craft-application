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
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Error classes for craft-application.

All errors inherit from craft_cli.CraftError.
"""
from __future__ import annotations

import os
from collections.abc import Sequence
from typing import TYPE_CHECKING

import yaml
from craft_cli import CraftError
from craft_providers import bases

from craft_application import models
from craft_application.util.error_formatting import format_pydantic_errors
from craft_application.util.string import humanize_list

if TYPE_CHECKING:  # pragma: no cover
    import craft_parts
    import pydantic
    from typing_extensions import Self


class ProjectFileMissingError(CraftError, FileNotFoundError):
    """Error finding project file."""


class PathInvalidError(CraftError, OSError):
    """Error that the given path is not usable."""


class YamlError(CraftError, yaml.YAMLError):
    """Craft-cli friendly version of a YAML error."""

    @classmethod
    def from_yaml_error(cls, filename: str, error: yaml.YAMLError) -> Self:
        """Convert a pyyaml YAMLError to a craft-application YamlError."""
        message = f"error parsing {filename!r}"
        if isinstance(error, yaml.MarkedYAMLError):
            message += f": {error.problem}"
        details = str(error)
        return cls(
            message,
            details=details,
            resolution=f"Ensure {filename} contains valid YAML",
        )


class CraftValidationError(CraftError):
    """Error validating project yaml."""

    @classmethod
    def from_pydantic(
        cls,
        error: pydantic.ValidationError,
        *,
        file_name: str = "yaml file",
        **kwargs: str | bool | int | None,
    ) -> Self:
        """Convert this error from a pydantic ValidationError.

        :param error: The pydantic error to convert
        :param file_name: An optional file name of the malformed yaml file
        :param doc_slug: The optional slug to this error's docs.
        :param kwargs: additional keyword arguments get passed to CraftError
        """
        message = format_pydantic_errors(error.errors(), file_name=file_name)
        return cls(message, **kwargs)  # type: ignore[arg-type]


class PartsLifecycleError(CraftError):
    """Error during parts processing."""

    @classmethod
    def from_parts_error(cls, err: craft_parts.PartsError) -> Self:
        """Shortcut to create a PartsLifecycleError from a PartsError."""
        return cls(
            message=err.brief,
            details=err.details,
            resolution=err.resolution,
            doc_slug=err.doc_slug,
        )

    @classmethod
    def from_os_error(cls, err: OSError) -> Self:
        """Create a PartsLifecycleError from an OSError."""
        message = f"{err.filename}: {err.strerror}" if err.filename else err.strerror
        details = err.__class__.__name__
        if err.filename:
            details += f": filename: {err.filename!r}"
        if err.filename2:
            details += f", filename2: {err.filename2!r}"
        return cls(message, details=details)


class SecretsCommandError(CraftError):
    """Error when rendering a build-secret."""

    def __init__(self, host_directive: str, error_message: str) -> None:
        message = f'Error when processing secret "{host_directive}"'
        details = f"Command output: {error_message}"
        super().__init__(message=message, details=details)


class SecretsFieldError(CraftError):
    """Error when using a build-secret in a disallowed field."""

    def __init__(self, host_directive: str, field_name: str) -> None:
        message = (
            f'Build secret "{host_directive}" is not allowed on field "{field_name}"'
        )
        super().__init__(message=message)


class SecretsManagedError(CraftError):
    """A secret value was not found while in managed mode."""

    def __init__(self, host_directive: str) -> None:
        message = (
            f'Build secret "{host_directive}" was not found in the managed environment.'
        )
        super().__init__(message=message)


class InvalidPlatformError(CraftError):
    """The selected build plan platform is invalid."""

    def __init__(self, platform: str, all_platforms: Sequence[str]) -> None:
        message = f"Platform {platform!r} not found in the project definition."
        details = f"Valid platforms are: {', '.join(all_platforms)}."

        super().__init__(message=message, details=details)


class EmptyBuildPlanError(CraftError):
    """The build plan filtered out all possible builds."""

    def __init__(self) -> None:
        message = "No build matches the current execution environment."
        resolution = (
            "Check the project's 'platforms' declaration, and the "
            "'--platform' and '--build-for' parameters."
        )

        super().__init__(message=message, resolution=resolution)


class MultipleBuildsError(CraftError):
    """The build plan contains multiple possible builds."""

    def __init__(self, matching_builds: list[models.BuildInfo] | None = None) -> None:
        message = "Multiple builds match the current platform"
        if matching_builds:
            message += ": " + humanize_list(
                [build.platform for build in matching_builds],
                conjunction="and",
            )
        message += "."
        resolution = 'Check the "--platform" and "--build-for" parameters.'

        super().__init__(message=message, resolution=resolution)


class IncompatibleBaseError(CraftError):
    """The build plan's base is incompatible with the host environment."""

    def __init__(self, host_base: bases.BaseName, build_base: bases.BaseName) -> None:
        host_pretty = f"{host_base.name.title()} {host_base.version}"
        build_pretty = f"{build_base.name.title()} {build_base.version}"

        message = (
            f"{build_pretty} builds cannot be performed on this {host_pretty} system."
        )
        details = (
            "Builds must be performed on a specific system to ensure that the "
            "final artefact's binaries are compatible with the intended execution "
            "environment."
        )
        resolution = "Run a managed build, or run on a compatible host."
        retcode = os.EX_CONFIG

        super().__init__(
            message=message, details=details, resolution=resolution, retcode=retcode
        )


class InvalidParameterError(CraftError):
    """Invalid parameter or environment variable."""

    def __init__(self, parameter: str, value: str) -> None:
        message = f"Value '{value}' is invalid for parameter {parameter!r}."

        super().__init__(message=message)


class RemoteBuildError(CraftError):
    """Errors related to remote builds."""


class CancelFailedError(RemoteBuildError):
    """Builds could not be cancelled."""

    def __init__(  # (too many arguments)
        self,
        builds: Sequence[str],
        *,
        resolution: str | None = None,
        docs_url: str | None = None,
        logpath_report: bool = True,
        reportable: bool = True,
        retcode: int = 1,
    ) -> None:
        if len(builds) == 1:
            message = "Build could not be cancelled."
        else:
            message = f"{len(builds)} builds could not be cancelled."

        details = "\n".join(builds)

        super().__init__(
            message,
            details=details,
            resolution=resolution,
            docs_url=docs_url,
            logpath_report=logpath_report,
            reportable=reportable,
            retcode=retcode,
        )
