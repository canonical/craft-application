# This file is part of craft-application.
#
# Copyright 2024 Canonical Ltd.
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
"""Unit tests for the configuration service."""

import io
import itertools
import json
import string
import subprocess
from collections.abc import Iterator
from unittest import mock

import craft_application
import craft_cli
import pytest
import pytest_subprocess
import snaphelpers
from craft_application import launchpad
from craft_application.services import config
from hypothesis import given, strategies

CRAFT_APPLICATION_TEST_ENTRY_VALUES = [
    *(
        ("verbosity_level", mode.name.lower(), mode)
        for mode in craft_cli.messages.EmitterMode
    ),
    *(("verbosity_level", mode.name, mode) for mode in craft_cli.messages.EmitterMode),
    ("debug", "true", True),
    ("debug", "false", False),
    ("build_environment", "host", "host"),
    ("secrets", "Cara likes Butterscotch.", "Cara likes Butterscotch."),
    ("platform", "laptop", "laptop"),
    ("platform", "mainframe", "mainframe"),
    ("build_for", "riscv64", "riscv64"),
    ("build_for", "s390x", "s390x"),
    *(("parallel_build_count", str(i), i) for i in range(10)),
    *(("max_parallel_build_count", str(i), i) for i in range(10)),
]
APP_SPECIFIC_TEST_ENTRY_VALUES = [
    ("my_str", "some string", "some string"),
    ("my_int", "1", 1),
    ("my_int", "2", 2),
    ("my_bool", "true", True),
    ("my_bool", "false", False),
    ("my_default_str", "something", "something"),
    ("my_default_int", "4294967296", 2**32),
    ("my_bool", "1", True),
    ("my_arch", "riscv64", launchpad.Architecture.RISCV64),
]
TEST_ENTRY_VALUES = CRAFT_APPLICATION_TEST_ENTRY_VALUES + APP_SPECIFIC_TEST_ENTRY_VALUES


@pytest.fixture(scope="module")
def app_environment_handler(default_app_metadata) -> config.AppEnvironmentHandler:
    return config.AppEnvironmentHandler(default_app_metadata)


@pytest.fixture(scope="module")
def craft_environment_handler(default_app_metadata) -> config.CraftEnvironmentHandler:
    return config.CraftEnvironmentHandler(default_app_metadata)


@pytest.fixture(scope="module")
def snap_config_handler(default_app_metadata) -> Iterator[config.SnapConfigHandler]:
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("SNAP", "/snap/testcraft/x1")
        monkeypatch.setenv("SNAP_COMMON", "/")
        monkeypatch.setenv("SNAP_DATA", "/")
        monkeypatch.setenv("SNAP_REAL_HOME", "/")
        monkeypatch.setenv("SNAP_USER_COMMON", "/")
        monkeypatch.setenv("SNAP_USER_DATA", "/")
        monkeypatch.setenv("SNAP_INSTANCE_NAME", "testcraft")
        monkeypatch.setenv("SNAP_INSTANCE_KEY", "")
        yield config.SnapConfigHandler(default_app_metadata)


@pytest.fixture(scope="module")
def default_config_handler(default_app_metadata) -> config.DefaultConfigHandler:
    return config.DefaultConfigHandler(default_app_metadata)


@given(
    item=strategies.text(alphabet=string.ascii_letters + "_", min_size=1),
    content=strategies.text(
        alphabet=strategies.characters(categories=["L", "M", "N", "P", "S", "Z"])
    ),
)
def test_app_environment_handler(app_environment_handler, item: str, content: str):
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv(f"TESTCRAFT_{item.upper()}", content)

        assert app_environment_handler.get_raw(item) == content


@given(
    item=strategies.sampled_from(list(craft_application.ConfigModel.model_fields)),
    content=strategies.text(
        alphabet=strategies.characters(categories=["L", "M", "N", "P", "S", "Z"])
    ),
)
def test_craft_environment_handler(craft_environment_handler, item: str, content: str):
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv(f"CRAFT_{item.upper()}", content)

        assert craft_environment_handler.get_raw(item) == content


@pytest.mark.parametrize(("item", "content", "_"), CRAFT_APPLICATION_TEST_ENTRY_VALUES)
@pytest.mark.usefixtures("_")
def test_craft_environment_handler_success(
    monkeypatch, craft_environment_handler, item: str, content: str
):
    monkeypatch.setenv(f"CRAFT_{item.upper()}", content)

    assert craft_environment_handler.get_raw(item) == content


@pytest.mark.parametrize(("item", "content", "_"), APP_SPECIFIC_TEST_ENTRY_VALUES)
@pytest.mark.usefixtures("_")
def test_craft_environment_handler_error(
    monkeypatch, craft_environment_handler, item: str, content: str
):
    monkeypatch.setenv(f"CRAFT_{item.upper()}", content)

    with pytest.raises(KeyError):
        assert craft_environment_handler.get_raw(item) == content


@pytest.mark.parametrize(
    "error",
    [
        KeyError("SNAP_INSTANCE_NAME something or other"),
        snaphelpers.SnapCtlError(
            mock.Mock(returncode=1, stderr=io.BytesIO(b"snapd socket asplode"))
        ),
    ],
)
def test_snap_config_handler_create_error(mocker, default_app_metadata, error):
    mocker.patch("snaphelpers.is_snap", return_value=True)
    mock_snap_config = mocker.patch(
        "snaphelpers.SnapConfig",
        side_effect=error,
    )
    with pytest.raises(OSError, match="Not running as a snap."):
        config.SnapConfigHandler(default_app_metadata)

    mock_snap_config.assert_called_once_with()


def test_snap_config_handler_not_snap(mocker, default_app_metadata):
    mock_is_snap = mocker.patch("snaphelpers.is_snap", return_value=False)

    with pytest.raises(OSError, match="Not running as a snap."):
        config.SnapConfigHandler(default_app_metadata)

    mock_is_snap.asssert_called_once_with()


@given(
    item=strategies.text(alphabet=string.ascii_letters + "_", min_size=1),
    content=strategies.text(
        alphabet=strategies.characters(categories=["L", "M", "N", "P", "S", "Z"])
    ),
)
def test_snap_config_handler(snap_config_handler, item: str, content: str):
    snap_item = item.replace("_", "-")
    with pytest_subprocess.FakeProcess.context() as fp, pytest.MonkeyPatch.context() as mp:
        mp.setattr("snaphelpers._ctl.Popen", subprocess.Popen)
        fp.register(
            ["/usr/bin/snapctl", "get", "-d", snap_item],
            stdout=json.dumps({snap_item: content}),
        )
        assert snap_config_handler.get_raw(item) == content


@pytest.mark.parametrize(
    ("item", "expected"),
    [
        ("verbosity_level", craft_cli.EmitterMode.BRIEF),
        ("debug", False),
        ("lxd_remote", "local"),
        ("launchpad_instance", "production"),
        # Application model items with defaults
        ("my_default_str", "default"),
        ("my_default_int", -1),
        ("my_default_bool", True),
        ("my_default_factory", {"dict": "yes"}),
    ],
)
def test_default_config_handler_success(default_config_handler, item, expected):
    assert default_config_handler.get_raw(item) == expected


@pytest.mark.parametrize(
    ("item", "environment_variables", "expected"),
    [
        ("verbosity_level", {}, craft_cli.EmitterMode.BRIEF),
        *(
            ("verbosity_level", {"TESTCRAFT_VERBOSITY_LEVEL": mode.name}, mode)
            for mode in craft_cli.EmitterMode
        ),
        *(
            ("verbosity_level", {"TESTCRAFT_VERBOSITY_LEVEL": mode.name.lower()}, mode)
            for mode in craft_cli.EmitterMode
        ),
        *(
            ("verbosity_level", {"CRAFT_VERBOSITY_LEVEL": mode.name}, mode)
            for mode in craft_cli.EmitterMode
        ),
        *(
            ("verbosity_level", {"CRAFT_VERBOSITY_LEVEL": mode.name.lower()}, mode)
            for mode in craft_cli.EmitterMode
        ),
        *(
            ("debug", {var: value}, True)
            for var, value in itertools.product(
                ["CRAFT_DEBUG", "TESTCRAFT_DEBUG"], ["true", "1", "yes", "Y"]
            )
        ),
        *(
            ("debug", {var: value}, False)
            for var, value in itertools.product(
                ["CRAFT_DEBUG", "TESTCRAFT_DEBUG"], ["false", "0", "no", "N"]
            )
        ),
        *(
            ("parallel_build_count", {var: str(value)}, value)
            for var, value in itertools.product(
                ["CRAFT_PARALLEL_BUILD_COUNT", "TESTCRAFT_PARALLEL_BUILD_COUNT"],
                range(10),
            )
        ),
    ],
)
def test_config_service_converts_type(
    monkeypatch: pytest.MonkeyPatch,
    fake_process: pytest_subprocess.FakeProcess,
    fake_services,
    item: str,
    environment_variables: dict[str, str],
    expected,
):
    monkeypatch.setattr("snaphelpers._ctl.Popen", subprocess.Popen)
    for key, value in environment_variables.items():
        monkeypatch.setenv(key, value)
    fake_process.register(["/usr/bin/snapctl", fake_process.any()], stdout="{}")
    assert fake_services.config.get(item) == expected
