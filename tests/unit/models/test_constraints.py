# This file is part of craft-application.
#
# Copyright 2023 Canonical Ltd.
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
"""Tests for project model."""

import re
from string import ascii_letters, ascii_lowercase, digits
from typing import cast

import pydantic.errors
import pytest
from craft_application.models import constraints
from craft_application.models.constraints import (
    LicenseStr,
    ProjectName,
    ProprietaryLicenseStr,
    SpdxLicenseStr,
    VersionStr,
)
from hypothesis import given, strategies

ALPHA_NUMERIC = [*ascii_letters, *digits]
LOWER_ALPHA_NUMERIC = [*ascii_lowercase, *digits]
VERSION_STRING_VALID_CHARACTERS = [*ascii_letters, *digits, *":.+~-"]


# region Hypothesis strategies
def valid_project_name_strategy():
    """A strategy for a project name that matches all the project name rules.

    Rules may be viewed in the ProjectName docstring.
    """
    strategy = strategies.text(
        strategies.sampled_from([*LOWER_ALPHA_NUMERIC, "-"]), min_size=1, max_size=40
    )
    return strategy.filter(
        lambda name: all(
            (
                "--" not in name,
                not (name.startswith("-") or name.endswith("-")),
                re.match("[a-z]", name),
            )
        )
    )


def valid_title_strategy():
    stripped_title_min_length = 2
    return strategies.text(
        alphabet=strategies.characters(
            whitelist_categories=["L", "M", "N", "P", "S", "Z"]
        ),
        min_size=2,
        max_size=40,
    ).filter(lambda txt: len(txt.strip()) >= stripped_title_min_length)


def valid_version_strategy():
    return strategies.text(
        strategies.sampled_from(VERSION_STRING_VALID_CHARACTERS),
        min_size=1,
        max_size=32,
    ).filter(lambda version: version[0] in ALPHA_NUMERIC and version[-1] not in "-:.")


def string_or_unique_list():
    return strategies.one_of(
        strategies.none(),
        strategies.text(),
        strategies.lists(strategies.text(), unique=True),
    )


# endregion
# region Unique list values tests
@given(
    strategies.sets(
        strategies.one_of(
            strategies.none(),
            strategies.integers(),
            strategies.floats(),
            strategies.text(),
        )
    )
)
def test_validate_list_is_unique_hypothesis_success(values: set):
    values_list = list(values)
    constraints._validate_list_is_unique(values_list)


@pytest.mark.parametrize(
    "values", [[], [None], [None, 0], [None, 0, ""], [True, 2, "True", "2", "two"]]
)
def test_validate_list_is_unique_success(values: list):
    constraints._validate_list_is_unique(values)


@pytest.mark.parametrize(
    ("values", "expected_dupes_text"),
    [
        ([None, None], "[None]"),
        ([0, 0], "[0]"),
        ([1, True], "[1]"),
        ([True, 1], "[True]"),
        (["this", "that", "this"], "['this']"),
    ],
)
def test_validate_list_is_unique_with_duplicates(values, expected_dupes_text):
    with pytest.raises(ValueError, match="^duplicate values in list: ") as exc_info:
        constraints._validate_list_is_unique(values)

    assert exc_info.value.args[0].endswith(expected_dupes_text)


# endregion
# region ProjectName tests
class _ProjectNameModel(pydantic.BaseModel):
    name: ProjectName


@given(name=valid_project_name_strategy())
def test_valid_project_name_hypothesis(name):
    project = _ProjectNameModel(name=name)

    assert project.name == name


@pytest.mark.parametrize(
    "name",
    [
        "purealpha",
        "0start-and-end-numeric9",
        "0123start-with-multiple-digits",
        "end-with-multiple-digits6789",
        *(
            pytest.param(letter, id=f"single-letter-{letter}")
            for letter in ascii_lowercase
        ),
    ],
)
def test_valid_project_name(name):
    project = _ProjectNameModel(name=name)

    assert project.name == name


@pytest.mark.parametrize(
    "name",
    [
        pytest.param("", id="empty string"),
        "double--hyphen",
        "-hyphen-start",
        "hyphen-end-",
        "UpperCase",
    ],
)
def test_invalid_project_name(name):
    with pytest.raises(pydantic.ValidationError):
        _ProjectNameModel(name=name)


# endregion
# region VersionStr tests
class _VersionStrModel(pydantic.BaseModel):
    version: VersionStr


@given(version=strategies.integers(min_value=0, max_value=10**32 - 1))
def test_version_str_hypothesis_integers(version):
    version_str = str(version)
    _VersionStrModel(version=version_str)

    assert version_str == str(version)


@given(version=strategies.floats(min_value=0.0))
def test_version_str_hypothesis_floats(version):
    version_str = str(version)
    _VersionStrModel(version=version_str)

    assert version_str == str(version)


@given(version=valid_version_strategy())
def test_version_str_hypothesis(version):
    version_str = str(version)
    _VersionStrModel(version=version)

    assert version_str == str(version)


@pytest.mark.parametrize("version", ["0", "1.0", "1.0.0.post10+git12345678"])
def test_valid_version_str(version):
    version_str = str(version)
    _VersionStrModel(version=version)

    assert version_str == str(version)


@pytest.mark.parametrize("version", [""])
def test_invalid_version_str(version):
    with pytest.raises(pydantic.ValidationError):
        _VersionStrModel(version=str(version))


# endregion
# region SpdxLicenseStr tests

_VALID_SPDX_LICENCES = [
    "MIT",
    "GPL-3.0",
    "GPL-3.0+",
    "GPL-3.0+ and MIT",
    "LGPL-3.0+ or BSD-3-Clause",
]


@pytest.fixture(params=_VALID_SPDX_LICENCES)
def valid_spdx_license_str(request: pytest.FixtureRequest) -> str:
    return cast(str, request.param)


class _SpdxLicenseStrModel(pydantic.BaseModel):
    license: SpdxLicenseStr


def test_spdx_license_str_valid(valid_spdx_license_str: str) -> None:
    model = _SpdxLicenseStrModel(license=valid_spdx_license_str)
    assert model.license == valid_spdx_license_str


@pytest.mark.parametrize("license_str", ["Copyright 1990", "Proprietary"])
def test_spdx_license_str_invalid(license_str):
    with pytest.raises(pydantic.ValidationError) as validation_error:
        _ = _SpdxLicenseStrModel(license=license_str)
    assert validation_error.match(
        f"License '{license_str}' not valid. It must be in SPDX format.",
    )


def test_spdx_parser_with_none():
    from craft_application.models.constraints import _validate_spdx_license

    val = None
    with pytest.raises(
        ValueError, match=f"License '{val}' not valid. It must be in SPDX format."
    ):
        _validate_spdx_license(val)  # pyright: ignore[reportArgumentType]


# endregion
# region ProprietaryLicenseStr tests
class _ProprietaryLicenseStrModel(pydantic.BaseModel):
    license: ProprietaryLicenseStr


def test_proprietary_str_valid():
    model = _ProprietaryLicenseStrModel(license="proprietary")
    assert model.license == "proprietary"


def test_proprietary_str_invalid():
    with pytest.raises(pydantic.ValidationError) as validation_error:
        _ = _ProprietaryLicenseStrModel(
            license="non-proprietary"  # pyright: ignore[reportArgumentType]
        )
    assert validation_error.match("Input should be 'proprietary'")


# endregion
# region LicenseStr tests
class _LicenseStrModel(pydantic.BaseModel):
    license: LicenseStr


@pytest.mark.parametrize(
    "license_str",
    [*_VALID_SPDX_LICENCES, "proprietary"],
)
def test_license_str_valid(license_str):
    model = _LicenseStrModel(license=license_str)
    assert model.license == license_str


@pytest.mark.parametrize("license_str", ["Copyright 1990", "Proprietary"])
def test_license_str_invalid(license_str):
    with pytest.raises(pydantic.ValidationError) as validation_error:
        _ = _LicenseStrModel(license=license_str)
    assert validation_error.match(
        f"License '{license_str}' not valid. It must be in SPDX format.",
    )


def test_license_str_invalid_literal():
    with pytest.raises(pydantic.ValidationError) as validation_error:
        _ = _LicenseStrModel(
            license="non-proprietary"  # pyright: ignore[reportArgumentType]
        )
    assert validation_error.match("Input should be 'proprietary'")


# endregion
