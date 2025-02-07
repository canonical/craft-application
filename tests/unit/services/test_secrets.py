#  This file is part of craft-application.
#
#  Copyright 2024 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Unit tests for the Secrets service."""

from typing import cast
from unittest import mock

import craft_cli
import pytest
from hypothesis import HealthCheck, given, settings, strategies

from craft_application import errors
from craft_application.services import _secrets


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        pytest.param("", {}, id="empty-string"),
        pytest.param([], {}, id="empty-list"),
        pytest.param({}, {}, id="empty-dict"),
        pytest.param(set(), {}, id="empty-set"),
        pytest.param(0, {}, id="number"),
        pytest.param(True, {}, id="boolean"),
        pytest.param(None, {}, id="None"),
        pytest.param("The universe exists.", {}, id="non-secret-str"),
        pytest.param(
            "My favourite game: $(HOST_SECRET:sl)",
            {(): "$(HOST_SECRET:sl)"},
            id="secret-str",
        ),
        pytest.param(
            ["", "$(HOST_SECRET:sl)"], {(1,): "$(HOST_SECRET:sl)"}, id="secret-list"
        ),
        pytest.param(
            {"key": "$(HOST_SECRET:sl)"},
            {("key",): "$(HOST_SECRET:sl)"},
            id="secret-dict",
        ),
        pytest.param({"$(HOST_SECRET:sl)"}, {(): "$(HOST_SECRET:sl)"}, id="secret-set"),
        pytest.param(
            {
                "parts": {
                    "public-part": {"plugin": "dump", "source": "http://example.com"},
                    "private-part": {
                        "plugin": "dump",
                        "source": "https://me:$(HOST_SECRET:echo password)@secrets.local",
                    },
                    "env-part": {
                        "plugin": "nil",
                        "build-environment": [
                            {"NOT_SECRET": "Snaps are cool"},
                            {"SECRET": "$(HOST_SECRET:cat /dev/urandom)"},
                        ],
                    },
                    "invalid-secrets-part": {
                        "plugin": "$(HOST_SECRET:cat /part/name)",
                        "override-build": "echo $(HOST_SECRET:cat /part/name)",
                    },
                },
            },
            {
                ("parts", "private-part", "source"): "$(HOST_SECRET:echo password)",
                (
                    "parts",
                    "env-part",
                    "build-environment",
                    1,
                    "SECRET",
                ): "$(HOST_SECRET:cat /dev/urandom)",
                (
                    "parts",
                    "invalid-secrets-part",
                    "override-build",
                ): "$(HOST_SECRET:cat /part/name)",
                (
                    "parts",
                    "invalid-secrets-part",
                    "plugin",
                ): "$(HOST_SECRET:cat /part/name)",
            },
            id="parts-sample",
        ),
    ],
)
def test_find_secrets(data, expected):
    assert _secrets._find_secrets(data) == expected


STANDARD_SECRET = "eyJlY2hvICR7U0VDUkVUX0VOVl9WQVJ9IjogInZlcnkgc2VjcmV0In0="
SECRETS_RENDERED = [
    pytest.param({}, "e30=", id="empty_dict"),
    pytest.param(
        {"echo ${SECRET_ENV_VAR}": "very secret"},
        STANDARD_SECRET,
        id="secret-var",
    ),
]


@pytest.mark.parametrize(
    ("expected", "env"), [pytest.param({}, "", id="empty"), *SECRETS_RENDERED]
)
def test_load_from_environment(monkeypatch, env, expected):
    monkeypatch.setenv("CRAFT_SECRETS", env)

    assert _secrets._load_from_environment() == expected


@pytest.mark.parametrize("secrets", [{}, {"password for Moria": "Mellon"}])
@pytest.mark.parametrize("mode", craft_cli.EmitterMode)
def test_secrets_are_hidden(capsys, secrets_service, secrets, mode):
    craft_cli.emit.init(
        mode=mode, appname="testcraft", greeting="Speak friend and enter"
    )

    for name, value in secrets.items():
        secrets_service[name] = value
    craft_cli.emit.progress(str(secrets))
    craft_cli.emit.message(str(secrets))
    craft_cli.emit.progress(str(secrets_service.get_environment))
    craft_cli.emit.message(str(secrets_service.get_environment))

    stdout, stderr = capsys.readouterr()

    for name, value in secrets.items():
        if mode.value >= craft_cli.EmitterMode.BRIEF.value:
            assert name in stdout
            assert name in stderr

        assert value not in stdout
        assert value not in stderr


@pytest.mark.parametrize(("env", "expected"), SECRETS_RENDERED)
def test_get_environment(secrets_service: _secrets.SecretsService, env, expected):
    for key, value in env.items():
        secrets_service[key] = value

    assert secrets_service.get_environment()["CRAFT_SECRETS"] == expected


@given(key=strategies.text(min_size=1), value=strategies.text(min_size=1))
@settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
def test_get_environment_with_arbitrary_secrets(
    secrets_service, monkeypatch, key, value
):
    monkeypatch.delenv("CRAFT_SECRETS", raising=False)
    secrets_service.setup()
    secrets_service[key] = value

    serialised = secrets_service.get_environment()["CRAFT_SECRETS"]

    monkeypatch.setenv("CRAFT_SECRETS", serialised)

    assert _secrets._load_from_environment() == {key: value}


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        ({}, {}),
        (
            {
                "parts": {
                    "my-part": {
                        "source": "https://user:$(HOST_SECRET:echo password)@git.launchpad.net/secret-project"
                    }
                }
            },
            {
                "parts": {
                    "my-part": {
                        "source": "https://user:password@git.launchpad.net/secret-project"
                    }
                }
            },
        ),
        (
            {
                "parts": {
                    "my-part": {
                        "build-environment": [
                            {"SECRET": "$(HOST_SECRET:echo this is a secret)"}
                        ]
                    }
                }
            },
            {
                "parts": {
                    "my-part": {"build-environment": [{"SECRET": "this is a secret"}]}
                }
            },
        ),
    ],
)
def test_render_host_success(secrets_service: _secrets.SecretsService, data, expected):
    assert secrets_service.render(data) == expected


@pytest.mark.parametrize(
    "data",
    [
        {"parts": {"my-part": {"source": "$(HOST_SECRET:exit 1)"}}},
        {
            "parts": {
                "my-part": {"build-environment": [{"SECRET": "$(HOST_SECRET:false)"}]}
            }
        },
    ],
)
def test_render_host_command_error(secrets_service: _secrets.SecretsService, data):
    with pytest.raises(
        errors.SecretsCommandError, match=r'^Error when processing secret "\$\(.+\)"$'
    ):
        secrets_service.render(data)


@pytest.mark.parametrize(
    ("data", "fields"),
    [
        (
            {
                "secret": """$(HOST_SECRET:perl -e '$_="wftedskaebjgdpjgidbsmnjgc";tr/a-z/oh, turtleneck Phrase Jar!/; print;')"""
            },
            ["secret"],
        ),
        (
            {
                "parts": {
                    "my-part": {
                        "stage-snaps": ["astral-uv/$(HOST_SECRET:uv --version)"]
                    }
                }
            },
            ["parts.my-part.stage-snaps[0]: $(HOST_SECRET:uv --version)"],
        ),
    ],
)
def test_render_host_remaining_secrets(
    secrets_service: _secrets.SecretsService, data, fields
):
    with pytest.raises(
        errors.SecretsInFieldsError, match=r"^\d+ build secrets in disallowed fields:"
    ) as exc_info:
        secrets_service.render(data)

    for field in fields:
        assert f"\n - {field}" in cast(str, exc_info.value.details)


@pytest.mark.parametrize(
    ("data", "expected"),
    [
        (
            {"parts": {"my-part": {"source": "$(HOST_SECRET:echo ${SECRET_ENV_VAR})"}}},
            {"parts": {"my-part": {"source": "very secret"}}},
        ),
    ],
)
def test_render_managed_success(
    monkeypatch, secrets_service: _secrets.SecretsService, data, expected
):
    monkeypatch.setenv("CRAFT_MANAGED_MODE", "1")
    monkeypatch.setenv("CRAFT_SECRETS", STANDARD_SECRET)

    secrets_service.setup()
    assert secrets_service.render(data) == expected


@pytest.mark.parametrize(
    "data",
    [
        {"parts": {"my-part": {"source": "$(HOST_SECRET:echo ${NOT_SO_SECRET})"}}},
    ],
)
def test_render_managed_error(
    monkeypatch, secrets_service: _secrets.SecretsService, data
):
    monkeypatch.setenv("CRAFT_MANAGED_MODE", "1")
    monkeypatch.setenv("CRAFT_SECRETS", STANDARD_SECRET)
    mock_run_command = mock.Mock()
    monkeypatch.setattr(_secrets, "_run_command", mock_run_command)

    secrets_service.setup()
    with pytest.raises(errors.SecretsManagedError):
        secrets_service.render(data)

    mock_run_command.assert_not_called()
