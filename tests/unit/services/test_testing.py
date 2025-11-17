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
from collections.abc import Iterable
from typing import Any
from unittest import mock

import craft_application.services.testing
import craft_cli.messages
import craft_platforms
import pytest
from craft_application import models
from craft_application.services.testing import TestingService
from craft_cli import CraftError


@pytest.fixture(scope="module")
def testing_service(default_app_metadata) -> TestingService:
    return TestingService(
        app=default_app_metadata,
        services=mock.Mock(),  # TestingService doesn't rely on other services.
    )


@pytest.mark.parametrize("shell", [False, True])
@pytest.mark.parametrize("shell_after", [False, True])
@pytest.mark.parametrize("debug", [False, True])
@pytest.mark.parametrize("test_expressions", [[], ["exp1", "exp2"]])
@pytest.mark.parametrize("is_ci", [False, True])
def test_get_spread_command(
    testing_service: TestingService,
    check,
    mocker,
    monkeypatch,
    in_project_path: pathlib.Path,
    shell: bool,
    shell_after: bool,
    debug: bool,
    test_expressions: Iterable[str],
    is_ci: bool,
):
    # Set the CI environment variable to 1 if is_ci, or empty otherwise.
    monkeypatch.setenv("CI", "1" * int(is_ci))
    mocker.patch("shutil.which", return_value="/usr/local/bin/craft.spread")

    fake_distro = mocker.Mock()
    fake_distro.distribution = "mydistro"
    fake_distro.series = "99"
    mocker.patch(
        "craft_platforms.DistroBase.from_linux_distribution", return_value=fake_distro
    )
    mocker.patch(
        "craft_application.services.testing.TestingService._filter_spread_jobs",
        return_value=["craft:mydistro-99:my/suite/"],
    )

    actual = testing_service._get_spread_command(
        shell=shell,
        shell_after=shell_after,
        debug=debug,
        test_expressions=test_expressions,
    )

    if shell:
        check.is_in("-shell", actual)
    else:
        check.is_not_in("-shell", actual)
    if shell_after:
        check.is_in("-shell-after", actual)
    else:
        check.is_not_in("-shell-after", actual)
    if debug:
        check.is_in("-debug", actual)
    else:
        check.is_not_in("-debug", actual)

    if is_ci:
        if test_expressions:
            check.is_in("craft:mydistro-99:my/suite/", actual)
        else:
            check.is_in("craft:mydistro-99", actual)
    else:
        for expression in test_expressions:
            check.is_in(str(expression), actual)


def test_get_spread_command_no_jobs(
    testing_service: TestingService, mocker, monkeypatch
):
    # Set the CI environment variable to 1 if is_ci, or empty otherwise.
    monkeypatch.setenv("CI", "1")
    mocker.patch("shutil.which", return_value="spread")

    fake_distro = mocker.Mock()
    fake_distro.distribution = "mydistro"
    fake_distro.series = "99"
    mocker.patch(
        "craft_platforms.DistroBase.from_linux_distribution", return_value=fake_distro
    )
    mocker.patch(
        "craft_application.services.testing.TestingService._filter_spread_jobs",
        return_value=[],
    )

    with pytest.raises(CraftError) as raised:
        testing_service._get_spread_command(test_expressions=["exp1", "exp2"])

    assert str(raised.value) == "No matches for test the specified test filters."


@pytest.mark.parametrize(
    ("expressions", "run_spread_list", "cmdline"),
    [
        (["exp1", "exp2"], True, ["spread", "craft:mydistro-100:my/suite/"]),
        (["craft"], False, ["spread", "craft:mydistro-100"]),
        (["craft:"], False, ["spread", "craft:mydistro-100"]),
    ],
)
def test_get_spread_command_ci_expression(
    mocker,
    monkeypatch: pytest.MonkeyPatch,
    testing_service: TestingService,
    expressions: list[str],
    run_spread_list: bool,
    cmdline: list[str],
):
    # The jobs returned by `spread -list exp1 exp2`
    fake_proc = mock.Mock()
    fake_proc.stdout = (
        "backend:system:my/suite/\n"
        "craft:mydistro-100:my/suite/\n"
        "craft:mydistro-101:my/suite/"
    )

    monkeypatch.setenv("CI", "1")
    mocker.patch("shutil.which", return_value="spread")
    mock_run = mocker.patch("subprocess.run", return_value=fake_proc)

    fake_distro = mocker.Mock()
    fake_distro.distribution = "mydistro"
    fake_distro.series = "100"

    mocker.patch(
        "craft_platforms.DistroBase.from_linux_distribution", return_value=fake_distro
    )

    command = testing_service._get_spread_command(test_expressions=expressions)
    if run_spread_list:
        assert mock_run.mock_calls == [
            mock.call(
                ["spread", "-list", *expressions],
                capture_output=True,
                text=True,
                check=True,
                cwd=pathlib.Path.cwd(),
            )
        ]
    assert command == cmdline


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
    state = models.PackState(artifact=None, resources=None)
    with pytest.raises(CraftError, match="Could not find 'spread.yaml'"):
        testing_service.process_spread_yaml(new_dir / "wherever", state)


@pytest.mark.parametrize(
    ("env_var", "value", "testspec"),
    [("", "", "craft"), ("CI", "1", "craft:id-1.0")],
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
    monkeypatch.delenv("CI", raising=False)

    if env_var:
        monkeypatch.setenv(env_var, value)
    mocker.patch(
        "craft_platforms.DistroBase.from_linux_distribution",
        return_value=craft_platforms.DistroBase("id", "1.0"),
    )
    mocker.patch("shutil.which", return_value="spread")
    mock_run = mocker.patch("subprocess.run")

    testing_service.run_spread(tmp_path)
    assert mock_run.mock_calls == [
        mock.call(
            ["spread", testspec],
            check=True,
            stdout=mock.ANY,
            stderr=mock.ANY,
            cwd=tmp_path,
        ),
    ]


@pytest.mark.parametrize(
    ("shell", "shell_after", "debug", "flags", "streams"),
    [
        (True, False, False, ["-shell"], {}),
        (False, True, False, ["-shell-after"], {}),
        (False, False, True, ["-debug"], {}),
        (False, False, False, [], {"stdout": mock.ANY, "stderr": mock.ANY}),
    ],
)
def test_run_spread_interactive(
    tmp_path,
    mocker,
    testing_service: TestingService,
    shell: bool,
    shell_after: bool,
    debug: bool,
    flags: list[str],
    streams: dict[str, Any],
):
    mocker.patch("shutil.which", return_value="spread")
    mock_run = mocker.patch("subprocess.run")
    mock_emitter = mock.MagicMock(spec=craft_cli.messages.Emitter)
    mocker.patch.object(craft_application.services.testing, "emit", mock_emitter)

    fake_host = craft_platforms.DistroBase(distribution="ubuntu", series="24.04")
    mocker.patch.object(
        craft_platforms.DistroBase,
        "from_linux_distribution",
        return_value=fake_host,
    )

    testing_service.run_spread(
        tmp_path, shell=shell, shell_after=shell_after, debug=debug
    )
    assert mock_run.mock_calls == [
        mock.call(
            ["spread", *flags, mock.ANY],
            check=True,
            **streams,
            cwd=tmp_path,
        ),
    ]

    if shell or shell_after or debug:
        mock_emitter.pause.assert_called()
        mock_emitter.open_stream.assert_not_called()
    else:
        mock_emitter.pause.assert_not_called()
        mock_emitter.open_stream.assert_called()


@pytest.mark.parametrize(
    ("jobs", "prefix", "result"),
    [
        ([], "", []),
        (["b1:sys:job", "b2:sys:job"], "b", []),  # Partial string won't match
        (["b1:sys:job", "b2:sys:job"], "b1", ["b1:sys:job"]),
        (["b1:sys:job", "b2:sys:job"], "b1:sys", ["b1:sys:job"]),
        (["b1:sys:job", "b2:sys:job"], "b3", []),
    ],
)
def test_filter_spread_jobs(
    mocker,
    testing_service: TestingService,
    jobs: list[str],
    prefix: str,
    result: list[str],
):
    fake_proc = mock.Mock()
    fake_proc.stdout = "\n".join(jobs)

    mocker.patch("shutil.which", return_value="spread")
    mock_run = mocker.patch("subprocess.run", return_value=fake_proc)

    filtered = testing_service._filter_spread_jobs(["exp1", "exp2"], prefix=prefix)

    assert mock_run.mock_calls == [
        mock.call(
            ["spread", "-list", "exp1", "exp2"],
            capture_output=True,
            text=True,
            check=True,
            cwd=pathlib.Path.cwd(),
        )
    ]
    assert filtered == result
