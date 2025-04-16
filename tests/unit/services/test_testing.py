#  This file is part of craft-application.
#
#  Copyright 2024-2025 Canonical Ltd.
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
"""Unit tests for the TestingService."""

import pathlib
import stat
from unittest import mock

import pytest
from craft_cli import CraftError

from craft_application.services.testing import TestingService


@pytest.fixture(scope="module")
def testing_service(default_app_metadata) -> TestingService:
    return TestingService(
        app=default_app_metadata,
        services=mock.Mock(),  # TestingService doesn't rely on other services.
    )


@pytest.mark.parametrize("spread_name", ["craft.spread"])
def test_get_app_spread_executable_success(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    testing_service: TestingService,
    spread_name: str,
):
    spread_path = tmp_path / spread_name
    spread_path.touch()
    spread_path.chmod(spread_path.stat().st_mode | stat.S_IEXEC)
    monkeypatch.setenv("PATH", tmp_path.as_posix())

    assert testing_service._get_spread_executable() == spread_path.as_posix()


def test_get_app_spread_executable_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    testing_service: TestingService,
):
    monkeypatch.setenv("PATH", tmp_path.as_posix())

    with pytest.raises(
        CraftError, match="Internal error: cannot find a 'craft.spread' executable."
    ):
        testing_service._get_spread_executable()


def test_process_without_spread_file(new_dir, testing_service):
    with pytest.raises(CraftError, match="Could not find 'spread.yaml'"):
        testing_service.process_spread_yaml(new_dir / "wherever")


@pytest.mark.parametrize(
    ("env_var", "value", "testspec"), [("", "", "craft:"), ("CI", "1", "craft:id-1.0")]
)
def test_run_spread(
    testing_service: TestingService,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    env_var: str,
    value: str,
    testspec: str,
    mocker,
):
    monkeypatch.delenv("CI")

    if env_var:
        monkeypatch.setenv(env_var, value)
    mocker.patch("craft_application.os_release.OsRelease.id", return_value="id")
    mocker.patch(
        "craft_application.os_release.OsRelease.version_id", return_value="1.0"
    )
    mocker.patch("shutil.which", return_value="spread")
    mock_run = mocker.patch("subprocess.run")

    testing_service.run_spread(tmp_path)
    assert mock_run.mock_calls == [
        mock.call(
            ["spread", "-v", testspec],
            check=True,
            stdout=mock.ANY,
            stderr=mock.ANY,
            cwd=tmp_path,
        ),
    ]
