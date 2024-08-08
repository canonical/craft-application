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
"""Constrained pydantic types for *craft applications."""

import collections
import re
from collections.abc import Callable
from typing import Annotated, Literal, TypeVar

import license_expression  # type: ignore[import]
import pydantic
from pydantic_core import PydanticCustomError

T = TypeVar("T")
Tv = TypeVar("Tv")


def _validate_list_is_unique(value: list[T]) -> list[T]:
    value_set = set(value)
    if len(value_set) == len(value):
        return value
    dupes = [item for item, count in collections.Counter(value).items() if count > 1]
    raise ValueError(f"duplicate values in list: {dupes}")


def get_validator_by_regex(
    regex: re.Pattern[str], error_msg: str
) -> Callable[[str], str]:
    """Get a string validator by regular expression with a known error message.

    This allows providing better error messages for regex-based validation than the
    standard message provided by pydantic. Simply place the result of this function in
    a BeforeValidator attached to your annotated type.

    :param regex: a compiled regular expression on a string.
    :param error_msg: The error message to raise if the value is invalid.
    :returns: A validator function ready to be used by pydantic.BeforeValidator
    """

    def validate(value: str) -> str:
        """Validate the given string with the outer regex, raising the error message.

        :param value: a string to be validated
        :returns: that same string if it's valid.
        :raises: ValueError if the string is invalid.
        """
        value = str(value)
        if not regex.match(value):
            raise ValueError(error_msg)
        return value

    return validate


UniqueList = Annotated[
    list[T],
    pydantic.AfterValidator(_validate_list_is_unique),
    pydantic.Field(json_schema_extra={"uniqueItems": True}),
]

SingleEntryList = Annotated[
    list[T],
    pydantic.Field(min_length=1, max_length=1),
]

SingleEntryDict = Annotated[
    dict[T, Tv],
    pydantic.Field(min_length=1, max_length=1),
]

_PROJECT_NAME_DESCRIPTION = """\
The name of this project. This is used when uploading, publishing, or installing.

Project name rules:
* Valid characters are lower-case ASCII letters, numerals and hyphens.
* Must contain at least one letter
* May not start or end with a hyphen
* May not have two hyphens in a row
"""

_PROJECT_NAME_REGEX = r"^([a-z0-9][a-z0-9-]?)*[a-z]+([a-z0-9-]?[a-z0-9])*$"
_PROJECT_NAME_COMPILED_REGEX = re.compile(_PROJECT_NAME_REGEX)
MESSAGE_INVALID_NAME = (
    "invalid name: Names can only use ASCII lowercase letters, numbers, and hyphens. "
    "They must have at least one letter, may not start or end with a hyphen, "
    "and may not have two hyphens in a row."
)

ProjectName = Annotated[
    str,
    pydantic.BeforeValidator(
        get_validator_by_regex(_PROJECT_NAME_COMPILED_REGEX, MESSAGE_INVALID_NAME)
    ),
    pydantic.Field(
        min_length=1,
        max_length=40,
        strict=True,
        pattern=_PROJECT_NAME_REGEX,
        description=_PROJECT_NAME_DESCRIPTION,
        title="Project Name",
        examples=[
            "ubuntu",
            "jupyterlab-desktop",
            "lxd",
            "digikam",
            "kafka",
            "mysql-router-k8s",
        ],
    ),
]


ProjectTitle = Annotated[
    str,
    pydantic.Field(
        min_length=2,
        max_length=40,
        title="Title",
        description="A human-readable title.",
        examples=[
            "Ubuntu Linux",
            "Jupyter Lab Desktop",
            "LXD",
            "DigiKam",
            "Apache Kafka",
            "MySQL Router K8s charm",
        ],
    ),
]

SummaryStr = Annotated[
    str,
    pydantic.Field(
        max_length=78,
        title="Summary",
        description="A short description of your project.",
        examples=[
            "Linux for Human Beings",
            "The cross-platform desktop application for JupyterLab",
            "Container and VM manager",
            "Photo Management Program",
            "Charm for routing MySQL databases in Kubernetes",
            "An open-source event streaming platform for high-performance data pipelines",
        ],
    ),
]

UniqueStrList = UniqueList[str]

_VERSION_STR_REGEX = r"^[a-zA-Z0-9](?:[a-zA-Z0-9:.+~-]*[a-zA-Z0-9+~])?$"
_VERSION_STR_COMPILED_REGEX = re.compile(_VERSION_STR_REGEX)
MESSAGE_INVALID_VERSION = (
    "invalid version: Valid versions consist of upper- and lower-case "
    "alphanumeric characters, as well as periods, colons, plus signs, tildes, "
    "and hyphens. They cannot begin with a period, colon, plus sign, tilde, or "
    "hyphen. They cannot end with a period, colon, or hyphen."
)

VersionStr = Annotated[
    str,
    pydantic.BeforeValidator(
        get_validator_by_regex(_VERSION_STR_COMPILED_REGEX, MESSAGE_INVALID_VERSION)
    ),
    pydantic.Field(
        max_length=32,
        pattern=_VERSION_STR_REGEX,
        strict=False,
        coerce_numbers_to_str=True,
        title="version string",
        description="A string containing the version of the project",
        examples=[
            "0.1",
            "1.0.0",
            "v1.0.0",
            "24.04",
        ],
    ),
]
"""A valid version string.

Should match snapd valid versions:
https://github.com/snapcore/snapd/blame/a39482ead58bf06cddbc0d3ffad3c17dfcf39913/snap/validate.go#L96
Applications may use a different set of constraints if necessary, but
ideally they will retain this same constraint.
"""


def _parse_spdx_license(value: str) -> license_expression.LicenseExpression:
    licensing = license_expression.get_spdx_licensing()
    if (
        lic := licensing.parse(  # pyright: ignore[reportUnknownMemberType]
            value, validate=True
        )
    ) is not None:
        return lic
    raise ValueError


def _validate_spdx_license(value: str) -> str:
    """Ensure the provided licence is a valid SPDX licence."""
    try:
        _ = _parse_spdx_license(value)
    except (license_expression.ExpressionError, ValueError):
        raise PydanticCustomError(
            "not_spdx_license",
            "License '{wrong_license}' not valid. It must be in SPDX format.",
            {"wrong_license": value},
        ) from None
    else:
        return value


SpdxLicenseStr = Annotated[
    str,
    pydantic.AfterValidator(_validate_spdx_license),
    pydantic.Field(
        title="License",
        description="SPDX license string.",
        examples=[
            "GPL-3.0",
            "MIT",
            "LGPL-3.0-or-later",
            "GPL-3.0+ and MIT",
        ],
    ),
]

ProprietaryLicenseStr = Literal["proprietary"]

LicenseStr = SpdxLicenseStr | ProprietaryLicenseStr
