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
"""Tests for error classes."""

import textwrap

import craft_parts
import pydantic
import pytest
import pytest_check
import yaml
from craft_application.errors import (
    CraftValidationError,
    InvalidUbuntuProBaseError,
    InvalidUbuntuProServiceError,
    InvalidUbuntuProStatusError,
    PartsLifecycleError,
    UbuntuProAttachedError,
    UbuntuProClientNotFoundError,
    UbuntuProDetachedError,
    YamlError,
)
from pydantic import BaseModel
from typing_extensions import Self


@pytest.mark.parametrize(
    ("original", "expected"),
    [
        (
            yaml.YAMLError("I am a thing"),
            YamlError(
                "error parsing 'something.yaml'",
                details="I am a thing",
                resolution="Ensure something.yaml contains valid YAML",
            ),
        ),
        (
            yaml.MarkedYAMLError(
                problem="I am a thing",
                problem_mark=yaml.error.Mark(
                    name="bork",
                    index=0,
                    line=0,
                    column=0,
                    buffer="Hello there",
                    pointer=0,
                ),
            ),
            YamlError(
                "error parsing 'something.yaml': I am a thing",
                details='I am a thing\n  in "bork", line 1, column 1:\n    Hello there\n    ^',
                resolution="Ensure something.yaml contains valid YAML",
            ),
        ),
    ],
)
def test_yaml_error_from_yaml_error(original, expected):
    actual = YamlError.from_yaml_error("something.yaml", original)

    assert actual == expected


@pytest.mark.parametrize(
    "err",
    [
        craft_parts.PartsError("Yo"),
        craft_parts.PartsError(brief="yo", details="sup", resolution="IDK fix it"),
    ],
)
def test_parts_lifecycle_error_from_parts_error(err):
    actual = PartsLifecycleError.from_parts_error(err)

    pytest_check.equal(err.brief, actual.args[0])
    pytest_check.equal(err.details, actual.details)
    pytest_check.equal(err.resolution, actual.resolution)


@pytest.mark.parametrize(
    ("err", "expected"),
    [
        (OSError(0, "strerror"), PartsLifecycleError("strerror", details="OSError")),
        (
            OSError(1, "some error string", "/some/file"),
            PartsLifecycleError(
                "/some/file: some error string",
                details="PermissionError: filename: '/some/file'",
            ),
        ),
        (
            OSError(2, "not found", "/file", None, "/another"),
            PartsLifecycleError(
                "/file: not found",
                details="FileNotFoundError: filename: '/file', filename2: '/another'",
            ),
        ),
    ],
)
def test_parts_lifecycle_error_from_os_error(
    err: OSError, expected: PartsLifecycleError
):
    actual = PartsLifecycleError.from_os_error(err)

    assert actual == expected


class Model(BaseModel):
    gt_int: int = pydantic.Field(gt=42)
    a_float: float
    b_int: int = 0

    @pydantic.model_validator(mode="after")
    def b_smaller_gt(self) -> Self:
        if self.b_int >= self.gt_int:
            raise ValueError("'b_int' must be smaller than 'gt_int'")
        return self


def test_validation_error_from_pydantic():
    data = {"gt_int": 21, "a_float": "not a float"}
    try:
        Model(**data)
    except pydantic.ValidationError as e:
        err = CraftValidationError.from_pydantic(e, file_name="myfile.yaml")
    else:  # pragma: no cover
        pytest.fail("Model failed to fail to validate!")

    expected = textwrap.dedent(
        """\
        Bad myfile.yaml content:
        - input should be greater than 42 (in field 'gt_int', input: 21)
        - input should be a valid number, unable to parse string as a number (in field 'a_float', input: 'not a float')"""
    )

    message = str(err)
    assert message == expected


def test_validation_error_from_pydantic_model():
    data = {"gt_int": 100, "a_float": 1.0, "b_int": 3000}
    try:
        Model(**data)
    except pydantic.ValidationError as e:
        err = CraftValidationError.from_pydantic(e, file_name="myfile.yaml")
    else:  # pragma: no cover
        pytest.fail("Model failed to fail to validate!")

    expected = textwrap.dedent(
        """
        Bad myfile.yaml content:
        - 'b_int' must be smaller than 'gt_int'
        """
    ).strip()

    message = str(err)
    assert message == expected


def test_ubuntu_pro_client_not_found_error():
    err = UbuntuProClientNotFoundError("/usr/bin/pro")

    assert (
        str(err)
        == "The Ubuntu Pro client was not found on the system at '/usr/bin/pro'"
    )


def test_ubuntu_pro_detached_error():
    err = UbuntuProDetachedError()

    assert str(err) == "Ubuntu Pro is requested, but was found detached."
    assert err.resolution is not None
    assert (
        err.resolution
        == "Attach Ubuntu Pro to continue. See 'pro' command for details."
    )


def test_ubuntu_pro_attached_error():
    err = UbuntuProAttachedError()

    assert str(err) == "Ubuntu Pro is not requested, but was found attached."
    assert err.resolution is not None
    assert (
        err.resolution
        == "Detach Ubuntu Pro to continue. See 'pro' command for details."
    )


@pytest.mark.parametrize(
    ("invalid_services", "expected"),
    [
        pytest.param({"bad-service"}, "bad-service", id="simple"),
        pytest.param(
            {"a-service", "z-service"}, "a-service, z-service", id="multiple-sorted"
        ),
        pytest.param(
            {"z-service", "a-service"}, "a-service, z-service", id="multiple-unsorted"
        ),
        pytest.param(None, "", id="none"),
    ],
)
def test_invalid_ubuntu_pro_service_error(invalid_services, expected):
    err = InvalidUbuntuProServiceError(invalid_services)

    assert str(err) == "Invalid Ubuntu Pro Services were requested."
    assert err.resolution is not None
    assert err.resolution == (
        "The services listed are either not supported by this application "
        "or are invalid Ubuntu Pro Services.\n"
        f"Invalid Services: {expected}\n"
        "See '--pro' argument details for supported services."
    )


def test_invalid_ubuntu_pro_base_error():
    err = InvalidUbuntuProBaseError("base", "devel")

    assert str(err) == "Ubuntu Pro builds are not supported on 'devel' base."
    assert err.resolution is not None
    assert err.resolution == "Remove '--pro' argument or set base to a supported base."


@pytest.mark.parametrize(
    ("requested", "available", "env", "expected"),
    [
        pytest.param(
            {"esm-apps"},
            set(),
            {"container": "lxc"},
            (
                "Enable or disable the following services.\n"
                "Enable: esm-apps\n"
                "See 'pro' command for details."
            ),
            id="container-enabled",
        ),
        pytest.param(
            set(),
            {"fips-updates"},
            {"container": "lxc"},
            (
                "Enable or disable the following services.\n"
                "Disable: fips-updates\n"
                "See 'pro' command for details."
            ),
            id="container-disabled",
        ),
        pytest.param(
            {"esm-apps"},
            {"fips-updates"},
            {"container": "lxc"},
            (
                "Enable or disable the following services.\n"
                "Enable: esm-apps\n"
                "Disable: fips-updates\n"
                "See 'pro' command for details."
            ),
            id="container-enabled-and-disabled",
        ),
        pytest.param(
            {"a-service", "b-service"},
            {"c-service", "d-service"},
            {"container": "lxc"},
            (
                "Enable or disable the following services.\n"
                "Enable: a-service, b-service\n"
                "Disable: c-service, d-service\n"
                "See 'pro' command for details."
            ),
            id="multiple-sorted-services",
        ),
        pytest.param(
            {"b-service", "a-service"},
            {"d-service", "c-service"},
            {"container": "lxc"},
            (
                "Enable or disable the following services.\n"
                "Enable: a-service, b-service\n"
                "Disable: c-service, d-service\n"
                "See 'pro' command for details."
            ),
            id="multiple-unsorted-services",
        ),
        pytest.param(
            set(),
            set(),
            {"container": "lxc"},
            "See 'pro' command for details.",
            id="container-none",
        ),
        pytest.param(
            {"esm-apps"},
            {"fips-updates"},
            {"SNAP_INSTANCE_NAME": "mysnap"},
            "Run 'mysnap clean' to reset Ubuntu Pro services.",
            id="snap",
        ),
        pytest.param(
            {"esm-apps"},
            {"fips-updates"},
            {},
            "Use the application's 'clean' command to reset Ubuntu Pro services.",
            id="enabled-and-disabled-unknown",
        ),
        pytest.param(
            None,
            None,
            {},
            "Use the application's 'clean' command to reset Ubuntu Pro services.",
            id="unknown",
        ),
    ],
)
def test_invalid_ubuntu_pro_status_error(
    monkeypatch, requested, available, env, expected
):
    monkeypatch.delenv("container", raising=False)
    monkeypatch.delenv("SNAP_INSTANCE_NAME", raising=False)
    for key, val in env.items():
        monkeypatch.setenv(key, val)

    err = InvalidUbuntuProStatusError(requested, available)

    assert str(err) == "Incorrect Ubuntu Pro services are enabled."
    assert err.resolution is not None
    assert err.resolution == expected


@pytest.mark.parametrize(
    ("requested", "available", "env", "expected_details"),
    [
        pytest.param(
            {"esm-apps"},
            {"fips-updates"},
            {"container": "lxc"},
            None,
            id="container-no-details",
        ),
        pytest.param(
            set(),
            set(),
            {},
            None,
            id="empty-sets-no-details",
        ),
        pytest.param(
            None,
            None,
            {},
            None,
            id="none-no-details",
        ),
        pytest.param(
            {"esm-apps"},
            None,
            {},
            "Requested services: esm-apps",
            id="requested-only",
        ),
        pytest.param(
            None,
            {"fips-updates"},
            {},
            "Available services: fips-updates",
            id="available-only",
        ),
        pytest.param(
            {"esm-apps"},
            {"fips-updates"},
            {},
            "Requested services: esm-apps\nAvailable services: fips-updates",
            id="both",
        ),
        pytest.param(
            {"a-service", "b-service"},
            {"c-service", "d-service"},
            {},
            "Requested services: a-service, b-service\nAvailable services: c-service, d-service",
            id="multiple-sorted",
        ),
        pytest.param(
            {"b-service", "a-service"},
            {"d-service", "c-service"},
            {},
            "Requested services: a-service, b-service\nAvailable services: c-service, d-service",
            id="multiple-unsorted",
        ),
    ],
)
def test_invalid_ubuntu_pro_status_error_details(
    monkeypatch, requested, available, env, expected_details
):
    monkeypatch.delenv("container", raising=False)
    monkeypatch.delenv("SNAP_INSTANCE_NAME", raising=False)
    for key, val in env.items():
        monkeypatch.setenv(key, val)

    err = InvalidUbuntuProStatusError(requested, available)

    assert err.details == expected_details
