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
"""Tests for build secrets."""

import pytest
from craft_application import errors, secrets


@pytest.fixture
def good_yaml_data():
    p1_data = {
        "source": "the source secret is $(HOST_SECRET:echo ${SECRET_1})",
        "build-environment": [
            {"VAR1": "the env secret is $(HOST_SECRET:echo ${SECRET_2})"},
            {"VAR2": "some value"},
        ],
    }

    return {"parts": {"p1": p1_data}}


@pytest.mark.parametrize("managed_mode", [True, False])
def test_secrets_parts(monkeypatch, good_yaml_data, managed_mode):
    commands = {
        "echo ${SECRET_1}": "source-secret",
        "echo ${SECRET_2}": "env-secret",
    }
    encoded = secrets._encode_commands(commands)

    if not managed_mode:
        # Running on the "host"; the secrets will be obtained by running commands,
        # so we set some environment variables that those commands will use.
        monkeypatch.setenv("SECRET_1", "source-secret")
        monkeypatch.setenv("SECRET_2", "env-secret")
    else:
        # Managed mode; the secrets must necessarily come from the environment already.
        # Here we fake the work that the host application would have done: get the
        # secrets by running the commands, and then encode them into the environment
        # of the launched (managed) application.
        monkeypatch.setenv("CRAFT_SECRETS", encoded["CRAFT_SECRETS"])

    secret_values = secrets.render_secrets(good_yaml_data, managed_mode=managed_mode)

    assert secret_values.environment == encoded
    assert secret_values.secret_strings == {"source-secret", "env-secret"}

    p1_data = good_yaml_data["parts"]["p1"]
    assert p1_data["source"] == "the source secret is source-secret"
    assert p1_data["build-environment"][0]["VAR1"] == "the env secret is env-secret"

    # Check that the rest of the build-environment is preserved
    assert p1_data["build-environment"][1]["VAR2"] == "some value"


def test_secrets_command_error():
    yaml_data = {"parts": {"p1": {"source": "$(HOST_SECRET:echo ${I_DONT_EXIST})"}}}

    with pytest.raises(errors.SecretsCommandError) as exc:
        secrets.render_secrets(yaml_data, managed_mode=False)

    expected_message = (
        'Error when processing secret "$(HOST_SECRET:echo ${I_DONT_EXIST})"'
    )
    expected_details = "I_DONT_EXIST: unbound variable"

    error = exc.value
    assert str(error) == expected_message
    assert error.details is not None
    assert expected_details in error.details


def test_secrets_cache(mocker, monkeypatch):
    monkeypatch.setenv("SECRET_1", "secret")
    p1_data = {
        "source": "the source secret is $(HOST_SECRET:echo ${SECRET_1})",
        "build-environment": [
            {"VAR1": "the env secret is $(HOST_SECRET:echo ${SECRET_1})"}
        ],
    }
    yaml_data = {"parts": {"p1": p1_data}}

    spied_run = mocker.spy(secrets, "_run_command")
    secrets.render_secrets(yaml_data, managed_mode=False)

    # Even though the HOST_SECRET is used twice, only a single bash call is done because
    # the command is the same.
    spied_run.assert_called_once_with("echo ${SECRET_1}")


_SECRET = "$(HOST_SECRET:echo ${GIT_VERSION})"  # noqa: S105 (this is not a password)


@pytest.mark.parametrize(
    ("yaml_data", "field_name"),
    [
        # A basic string field
        ({"version": f"v{_SECRET}"}, "version"),
        # A list item
        ({"stage-packages": ["first", "second", _SECRET]}, "stage-packages"),
        # A dict value
        ({"parts": {"p1": {"source-version": f"v{_SECRET}"}}}, "source-version"),
    ],
)
def test_secrets_bad_field(monkeypatch, yaml_data, field_name):
    monkeypatch.setenv("GIT_VERSION", "1.0")

    with pytest.raises(errors.SecretsFieldError) as exc:
        secrets.render_secrets(yaml_data, managed_mode=False)

    expected_error = f'Build secret "{_SECRET}" is not allowed on field "{field_name}"'
    err = exc.value
    assert str(err) == expected_error


def test_secrets_encode_decode():
    commands = {
        "echo $VAR1": "var1-value",
        "echo $VAR2": "var2-value",
    }

    encoded = secrets._encode_commands(commands)
    decoded = secrets._decode_commands(encoded)

    assert decoded == commands


def test_secrets_encode_decode_empty():
    commands = {}

    encoded = secrets._encode_commands(commands)
    decoded = secrets._decode_commands(encoded)

    assert decoded == encoded == commands


def test_secrets_managed_missing_key(good_yaml_data):
    with pytest.raises(errors.SecretsManagedError) as exc:
        secrets.render_secrets(good_yaml_data, managed_mode=True)

    expected_message = 'Build secret "$(HOST_SECRET:echo ${SECRET_1})" was not found in the managed environment.'
    assert str(exc.value) == expected_message
