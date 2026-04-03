# This file is part of craft-application.
#
# Copyright 2026 Canonical Ltd.
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
"""Tests for ProServices utility class."""

import re
import subprocess
from contextlib import nullcontext
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from craft_application import errors, models
from craft_application.errors import UbuntuProAttachedError
from craft_application.util import ProServices
from craft_application.util.pro_services import _ValidatorOptions
from typing_extensions import ContextManager


@pytest.fixture
def mock_pro_executable(mocker, tmp_path) -> Path:
    executable = tmp_path / "pro"
    executable.touch()
    mocker.patch.object(ProServices, "_pro_executable", executable)
    return executable


@pytest.fixture
def mock_pro_api(mocker):
    """Mock attached and enabled services endpoints."""
    state = {"is_attached": False, "enabled_services": []}

    def fake_api_call(endpoint):
        if endpoint == "u.pro.status.is_attached.v1":
            return {"data": {"attributes": {"is_attached": state["is_attached"]}}}
        if endpoint == "u.pro.status.enabled_services.v1":
            services = [
                {"name": n, "variant_enabled": False, "variant_name": None}
                for n in state["enabled_services"]
            ]
            return {"data": {"attributes": {"enabled_services": services}}}
        raise ValueError(f"Unexpected endpoint: {endpoint}")

    mocker.patch.object(ProServices, "_pro_api_call", side_effect=fake_api_call)
    return state


@pytest.mark.parametrize(
    ("services", "expected"),
    [
        pytest.param(set(), "<ProServices: None>", id="empty"),
        pytest.param({"esm-apps"}, "<ProServices: esm-apps>", id="simple"),
        pytest.param(
            {"esm-apps", "fips-updates"},
            "<ProServices: esm-apps, fips-updates>",
            id="multiple-sorted",
        ),
        pytest.param(
            {"fips-updates", "esm-apps"},
            "<ProServices: esm-apps, fips-updates>",
            id="multiple-unsorted",
        ),
    ],
)
def test_str(services, expected):
    """Test str representation."""
    result = str(ProServices(services))

    assert result == expected


@pytest.mark.parametrize(
    ("csv", "expected"),
    [
        pytest.param(
            "esm-apps",
            ProServices(["esm-apps"]),
            id="simple",
        ),
        pytest.param(
            "esm-apps,fips-updates",
            ProServices(["esm-apps", "fips-updates"]),
            id="multiple",
        ),
        pytest.param(
            "esm-apps , fips-updates",
            ProServices(["esm-apps", "fips-updates"]),
            id="whitespace",
        ),
        pytest.param(
            "esm-apps,esm-apps",
            ProServices(["esm-apps"]),
            id="duplicates",
        ),
        pytest.param(
            "esm-apps,",
            ProServices(["esm-apps"]),
            id="trailing-comma",
        ),
        pytest.param(
            ",esm-apps",
            ProServices(["esm-apps"]),
            id="leading-comma",
        ),
        pytest.param(
            "esm-apps,,fips-updates",
            ProServices(["esm-apps", "fips-updates"]),
            id="empty-entry",
        ),
    ],
)
def test_from_csv(csv: str, expected: ProServices):
    assert ProServices.from_csv(csv) == expected


def test_pro_client_exists_no_executable(mocker):
    """Return false if there isn't a Pro executable."""
    mocker.patch.object(ProServices, "_pro_executable", None)

    assert ProServices._pro_client_exists() is False


def test_pro_client_exists_missing(mocker, tmp_path):
    """Return false if the class defines a Pro executable but it doesn't exist on disk."""
    mocker.patch.object(ProServices, "_pro_executable", tmp_path / "pro")

    assert ProServices._pro_client_exists() is False


def test_pro_client_exists(mocker, mock_pro_executable):
    """Return true if the Pro executable exists."""
    assert ProServices._pro_client_exists() is True


def test_pro_api_call_client_missing_error(mocker, tmp_path):
    """Error if the Pro executable is missing."""
    mocker.patch.object(ProServices, "_pro_executable", tmp_path / "pro")

    with pytest.raises(errors.UbuntuProClientNotFoundError):
        ProServices._pro_api_call("u.pro.status.is_attached.v1")


def test_pro_api_call_subprocess_error(mocker, mock_pro_executable):
    """Error on subprocess error."""
    mocker.patch(
        "craft_application.util.pro_services.subprocess.run",
        side_effect=OSError("test error"),
    )
    expected = re.escape(
        f"An error occurred while executing {str(mock_pro_executable)!r}."
    )

    with pytest.raises(errors.UbuntuProApiError, match=expected):
        ProServices._pro_api_call("u.pro.status.is_attached.v1")


def test_pro_api_call_nonzero_error(mocker, mock_pro_executable):
    """Error on non-zero return code."""
    mocker.patch(
        "craft_application.util.pro_services.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=1,
            stdout="test stdout",
            stderr="test stderr",
        ),
    )
    expected = re.escape(
        "The Ubuntu Pro client returned a non-zero status: 1. See log for more details."
    )

    with pytest.raises(errors.UbuntuProApiError, match=expected):
        ProServices._pro_api_call("u.pro.status.is_attached.v1")


def test_pro_api_call_invalid_json_error(mocker, mock_pro_executable):
    """Error on invalid json."""
    mocker.patch(
        "craft_application.util.pro_services.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout="not json {{",
            stderr="test stderr",
        ),
    )
    expected = re.escape(
        "Could not parse JSON response from the Ubuntu Pro client. See log for more details."
    )

    with pytest.raises(errors.UbuntuProApiError, match=expected):
        ProServices._pro_api_call("u.pro.status.is_attached.v1")


def test_pro_api_call_error_result(mocker, mock_pro_executable):
    """Error on failure response."""
    mocker.patch(
        "craft_application.util.pro_services.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"result": "failure"}',
            stderr="test stderr",
        ),
    )
    expected = re.escape(
        "The Ubuntu Pro API returned an error response. See log for more details"
    )

    with pytest.raises(errors.UbuntuProApiError, match=expected):
        ProServices._pro_api_call("u.pro.status.is_attached.v1")


def test_pro_api_call(mocker, mock_pro_executable):
    mocker.patch(
        "craft_application.util.pro_services.subprocess.run",
        return_value=subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout='{"result": "success", "data": {"attributes": {"is_attached": true}}}',
            stderr="test stderr",
        ),
    )

    result = ProServices._pro_api_call("u.pro.status.is_attached.v1")

    assert result == {
        "result": "success",
        "data": {"attributes": {"is_attached": True}},
    }


@pytest.mark.parametrize("attached", [True, False])
def test_is_pro_attached(mocker, attached):
    mocker.patch.object(
        ProServices,
        "_pro_api_call",
        return_value={"data": {"attributes": {"is_attached": attached}}},
    )

    assert ProServices._is_pro_attached() is attached


@pytest.mark.parametrize(
    ("enabled_names", "expected"),
    [
        pytest.param([], ProServices(), id="none-enabled"),
        pytest.param(["esm-apps"], ProServices(["esm-apps"]), id="simple"),
        pytest.param(
            ["esm-apps", "fips-updates"],
            ProServices(["esm-apps", "fips-updates"]),
            id="multiple",
        ),
        pytest.param(
            ["esm-apps", "unsupported-service"],
            ProServices(["esm-apps"]),
            id="unsupported-filtered-out",
        ),
        pytest.param(
            ["unsupported-service"],
            ProServices(),
            id="all-unsupported",
        ),
    ],
)
def test_get_pro_services(mocker, enabled_names, expected):
    enabled_services = [
        {"name": name, "variant_enabled": False, "variant_name": None}
        for name in enabled_names
    ]
    mocker.patch.object(
        ProServices,
        "_pro_api_call",
        return_value={"data": {"attributes": {"enabled_services": enabled_services}}},
    )

    services = ProServices._get_pro_services()

    assert services == expected


@pytest.mark.parametrize(
    ("services", "base", "build_base", "expectation"),
    [
        pytest.param(
            [], "ubuntu@24.04", None, nullcontext(), id="no-services-valid-base"
        ),
        pytest.param([], "devel", None, nullcontext(), id="no-services-devel-base-ok"),
        pytest.param(["esm-apps"], None, None, nullcontext(), id="services-no-base"),
        pytest.param(
            ["esm-apps"], "ubuntu@24.04", None, nullcontext(), id="services-valid-base"
        ),
        pytest.param(
            ["esm-apps"],
            "ubuntu@24.04",
            "ubuntu@24.04",
            nullcontext(),
            id="services-valid-build-base",
        ),
        pytest.param(
            ["esm-apps"],
            "devel",
            None,
            pytest.raises(errors.InvalidUbuntuProBaseError),
            id="services-devel-base",
        ),
        pytest.param(
            ["esm-apps"],
            None,
            "devel",
            pytest.raises(errors.InvalidUbuntuProBaseError),
            id="services-devel-build-base",
        ),
    ],
)
def test_validate_project(services, base, build_base, expectation):
    pro_services = ProServices(services)
    project = MagicMock(spec=models.Project)
    project.base = base
    project.build_base = build_base

    with expectation:
        pro_services.validate_project(project)


@pytest.mark.parametrize(
    ("is_attached", "enabled_services", "requested", "expectation"),
    [
        pytest.param(False, [], [], nullcontext(), id="detached-no-services"),
        pytest.param(
            True, ["esm-apps"], ["esm-apps"], nullcontext(), id="attached-matching"
        ),
        pytest.param(
            True,
            ["esm-apps", "fips-updates"],
            ["esm-apps", "fips-updates"],
            nullcontext(),
            id="attached-multiple-matching",
        ),
        pytest.param(
            True,
            ["esm-apps", "fips-updates"],
            ["esm-apps"],
            nullcontext(),
            id="attached-requested-subset",
        ),
        pytest.param(
            True,
            ["esm-apps"],
            [],
            pytest.raises(errors.UbuntuProAttachedError),
            id="attached-no-services-requested",
        ),
        pytest.param(
            False,
            [],
            ["esm-apps"],
            pytest.raises(errors.UbuntuProDetachedError),
            id="detached-services-requested",
        ),
        pytest.param(
            True,
            ["fips-updates"],
            ["esm-apps"],
            pytest.raises(errors.InvalidUbuntuProStatusError),
            id="wrong-services-enabled",
        ),
        pytest.param(
            True,
            ["esm-apps"],
            ["esm-apps", "not-a-service"],
            pytest.raises(errors.InvalidUbuntuProServiceError),
            id="invalid-service-name",
        ),
    ],
)
def test_validate_environment(
    mock_pro_api, is_attached, enabled_services, requested, expectation
):
    """Test validate_environment with default (full) options."""
    mock_pro_api["is_attached"] = is_attached
    mock_pro_api["enabled_services"] = enabled_services

    with expectation:
        ProServices(requested)._validate_environment()


@pytest.mark.parametrize(
    ("options", "is_attached", "enabled_services", "requested"),
    [
        pytest.param(
            _ValidatorOptions.AVAILABILITY,
            True,
            ["fips-updates"],
            ["esm-apps"],
            id="skip-enablement",
        ),
        pytest.param(
            _ValidatorOptions.ATTACHMENT,
            True,
            [],
            ["not-a-service"],
            id="skip-support-check",
        ),
        pytest.param(
            _ValidatorOptions.DEFAULT,
            True,
            ["esm-apps"],
            ["esm-apps"],
            id="default",
        ),
    ],
)
def test_validate_environment_options(
    mock_pro_api, options, is_attached, enabled_services, requested
):
    """Non-default ValidatorOptions skip specific checks."""
    mock_pro_api["is_attached"] = is_attached
    mock_pro_api["enabled_services"] = enabled_services

    ProServices(requested)._validate_environment(options=options)


@pytest.mark.parametrize(
    ("services", "expectation"),
    [
        (set(), nullcontext()),
        ({"esm-apps"}, pytest.raises(errors.UbuntuProClientNotFoundError)),
    ],
)
def test_validate_environment_client_not_found(mocker, services, expectation):
    """Validate when the Pro client doesn't exist."""
    mocker.patch.object(ProServices, "_pro_executable", None)

    with expectation:
        ProServices(services)._validate_environment()


@pytest.mark.parametrize(
    ("run_managed", "is_managed", "validate_environment", "validator_options"),
    [
        pytest.param(False, False, True, None, id="destructive-mode"),
        pytest.param(True, True, True, None, id="managed-mode-in-instance"),
        pytest.param(
            True,
            False,
            True,
            _ValidatorOptions.AVAILABILITY,
            id="managed-mode-on-host",
        ),
        pytest.param(False, True, False, None, id="unmanaged-mode-in-managed-instance"),
    ],
)
def test_check_pro_context(
    mocker, run_managed, is_managed, validate_environment, validator_options
):
    """Pro services are validated in the correct situations."""
    pro_services = mocker.MagicMock(spec=ProServices)
    ProServices.check_pro_context(
        pro_services, run_managed=run_managed, is_managed=is_managed
    )

    assert pro_services._validate_environment.called is validate_environment

    if validator_options is not None:
        for call in pro_services._validate_environment.call_args_list:
            assert call.kwargs["options"] == validator_options


@pytest.mark.parametrize(
    ("run_managed", "is_managed", "expectation"),
    [
        pytest.param(
            False, False, pytest.raises(UbuntuProAttachedError), id="destructive"
        ),
        pytest.param(
            True, True, pytest.raises(UbuntuProAttachedError), id="managed-in-inner"
        ),
        pytest.param(True, False, nullcontext(), id="managed-in-outer"),
    ],
)
def test_check_pro_context_attachment(
    mock_pro_api: dict[str, Any],
    run_managed: bool,
    is_managed: bool,
    expectation: ContextManager,
) -> None:
    mock_pro_api["enabled_services"] = []
    mock_pro_api["is_attached"] = True
    pro_services = ProServices()

    with expectation:
        pro_services.check_pro_context(run_managed=run_managed, is_managed=is_managed)
