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

import dataclasses
import pathlib
import stat
import textwrap
from collections.abc import Iterable
from textwrap import dedent
from typing import Any
from unittest import mock

import craft_application.services.testing
import craft_cli.messages
import craft_platforms
import pytest
from craft_application import models
from craft_application.errors import TestFileError, YamlError
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
    state = models.PackState(artifacts=[])
    with pytest.raises(CraftError, match="Could not find 'testcraft-test.yaml'"):
        testing_service.process_spread_yaml(new_dir / "wherever", state)


def test_process_spread_yaml_accepts_named_artifacts_only(
    testing_service: TestingService,
    tmp_path: pathlib.Path,
    mocker,
    monkeypatch: pytest.MonkeyPatch,
):
    spread_file = tmp_path / "spread.yaml"
    spread_file.write_text(
        dedent("""
            project: test-project
            backends:
              craft:
                systems:
                  - ubuntu-24.04:
            suites:
              spread/general/:
                summary: General tests
            """)
    )
    state = models.PackState(
        artifacts=[models.PackedArtifact(name="tools", path=pathlib.Path("tools.tar"))]
    )
    mocker.patch.object(
        testing_service,
        "_get_backend",
        return_value=models.SpreadBackend(type="adhoc"),
    )

    dest = tmp_path / "processed-spread.yaml"
    monkeypatch.chdir(tmp_path)
    testing_service.process_spread_yaml(dest, state)

    assert "CRAFT_ARTIFACT_TOOLS: $PROJECT_PATH/tools.tar" in dest.read_text()


def test_process_spread_yaml_requires_any_artifact(
    testing_service: TestingService,
    tmp_path: pathlib.Path,
    mocker,
    monkeypatch: pytest.MonkeyPatch,
):
    spread_file = tmp_path / "spread.yaml"
    spread_file.write_text(
        dedent("""
            project: test-project
            backends:
              craft:
                systems:
                  - ubuntu-24.04:
            suites:
              spread/general/:
                summary: General tests
            """)
    )
    state = models.PackState(artifacts=[])
    mocker.patch.object(
        testing_service,
        "_get_backend",
        return_value=models.SpreadBackend(type="adhoc"),
    )

    dest = tmp_path / "processed-spread.yaml"
    monkeypatch.chdir(tmp_path)
    with pytest.raises(CraftError, match="No .* files to test"):
        testing_service.process_spread_yaml(dest, state)


@pytest.mark.parametrize(
    ("content", "expected"),
    [
        pytest.param(
            "backends:\n  craft:\n    systems: []\nsuites: {}\n",
            True,
            id="craft-test-file",
        ),
        pytest.param(
            "backends:\n  other:\n    systems: []\nsuites: {}\n",
            False,
            id="not-a-craft-test-file",
        ),
        pytest.param("- item1\n- item2\n", False, id="not-a-dict"),
    ],
)
def test_is_craft_test_file(tmp_path, content, expected):
    """Return whether spread.yaml is a craft test file."""
    spread_path = tmp_path / "spread.yaml"
    spread_path.write_text(content)

    assert TestingService._is_craft_test_file(spread_path) is expected


def test_is_craft_test_file_read_error(tmp_path):
    """Error if spread.yaml can't be read."""
    spread_path = tmp_path / "spread.yaml"
    spread_path.mkdir()

    with pytest.raises(CraftError, match="Could not read"):
        TestingService._is_craft_test_file(spread_path)


def test_is_craft_test_file_invalid_yaml(tmp_path):
    """Error if spread.yaml is invalid yaml."""
    spread_path = tmp_path / "spread.yaml"
    spread_path.write_text("backends: [unclosed")

    with pytest.raises(YamlError):
        TestingService._is_craft_test_file(spread_path)


def test_parse_test_config_uses_craft_test_yaml(
    in_project_path: pathlib.Path, default_app_metadata, emitter
):
    """Prefer the test config file over spread.yaml"""
    testing_service = TestingService(app=default_app_metadata, services=mock.Mock())

    (in_project_path / "testcraft-test.yaml").write_text(
        "backends:\n  craft:\n    systems: []\nsuites: {}\n"
    )
    # A deprecated spread.yaml file with a craft backend should be ignored
    # when the test config file is present.
    (in_project_path / "spread.yaml").write_text(
        "backends:\n  craft:\n    systems: []\nsuites: {}\n"
    )

    testing_service.parse_test_config()

    emitter.assert_interactions(None)


def test_parse_test_config_spread_yaml(
    in_project_path: pathlib.Path, default_app_metadata, emitter
):
    """Warn when a spread.yaml is used."""
    testing_service = TestingService(app=default_app_metadata, services=mock.Mock())

    (in_project_path / "spread.yaml").write_text(
        "backends:\n  craft:\n    systems: []\nsuites: {}\n"
    )

    testing_service.parse_test_config()

    emitter.assert_warning(
        "'spread.yaml' is deprecated for 'testcraft test'. "
        "Rename it to 'testcraft-test.yaml' and "
        "remove the 'project' key, if defined."
    )


def test_parse_test_config_single_warning(
    in_project_path: pathlib.Path, default_app_metadata, emitter
):
    """The deprecation warning is only emitted once."""
    testing_service = TestingService(app=default_app_metadata, services=mock.Mock())

    (in_project_path / "spread.yaml").write_text(
        "backends:\n  craft:\n    systems: []\nsuites: {}\n"
    )

    testing_service.parse_test_config()
    testing_service.parse_test_config()

    warning_calls = [call for call in emitter.interactions if call.args[0] == "warning"]
    assert len(warning_calls) == 1


def test_parse_test_config_no_warning_in_managed_mode(
    in_project_path: pathlib.Path, default_app_metadata, emitter, managed_mode
):
    """The deprecation warning is suppressed inside managed instances."""
    testing_service = TestingService(app=default_app_metadata, services=mock.Mock())

    (in_project_path / "spread.yaml").write_text(
        "backends:\n  craft:\n    systems: []\nsuites: {}\n"
    )

    testing_service.parse_test_config()

    emitter.assert_interactions(None)


def test_parse_test_config_ignores_non_craft_test_spread_yaml(
    in_project_path: pathlib.Path, default_app_metadata, emitter
):
    """Ignore spread.yaml if it lacks a craft backend."""
    testing_service = TestingService(app=default_app_metadata, services=mock.Mock())

    (in_project_path / "spread.yaml").write_text(
        "backends:\n  other:\n    systems: []\nsuites: {}\n"
    )

    with pytest.raises(CraftError, match="Could not find 'testcraft-test.yaml'"):
        testing_service.parse_test_config()

    emitter.assert_interactions(None)


def test_parse_test_config_fallback_disabled(
    in_project_path: pathlib.Path, default_app_metadata, emitter
):
    """Error on parsing spread.yaml if allow_spread is False."""
    disabled_app_metadata = dataclasses.replace(
        default_app_metadata, allow_spread_yaml=False
    )
    testing_service = TestingService(
        app=disabled_app_metadata,
        services=mock.Mock(),
    )

    (in_project_path / "spread.yaml").write_text(
        "backends:\n  craft:\n    systems: []\nsuites: {}\n"
    )

    with pytest.raises(CraftError, match="'spread.yaml' cannot be used") as raised:
        testing_service.parse_test_config()

    assert raised.value.resolution is not None
    assert "testcraft-test.yaml" in raised.value.resolution
    emitter.assert_interactions(None)


def test_parse_test_config_ignores_project_key(
    in_project_path: pathlib.Path, default_app_metadata
):
    """A 'project' key in a spread.yaml is silently unused."""
    testing_service = TestingService(app=default_app_metadata, services=mock.Mock())

    (in_project_path / "spread.yaml").write_text(
        "project: my-project\nbackends:\n  craft:\n    systems: []\nsuites: {}\n"
    )

    parsed = testing_service.parse_test_config()

    assert isinstance(parsed, models.CraftSpreadYaml)
    assert parsed.project == "my-project"


def test_parse_test_config_app_test_yaml_rejects_legacy_keys(
    in_project_path: pathlib.Path, default_app_metadata
):
    """Unsupported keys, like `project`, raise an error when parsing a craft test file."""
    testing_service = TestingService(app=default_app_metadata, services=mock.Mock())

    (in_project_path / "testcraft-test.yaml").write_text(
        "project: my-project\nbackends:\n  craft:\n    systems: []\nsuites: {}\n"
    )

    with pytest.raises(TestFileError):
        testing_service.parse_test_config()


def test_process_spread_file(new_dir, monkeypatch, testing_service):
    monkeypatch.delenv("CI", raising=False)
    monkeypatch.delenv("OS_AUTH_TYPE", raising=False)
    monkeypatch.delenv("OS_AUTH_URL", raising=False)
    monkeypatch.delenv("OS_REGION_NAME", raising=False)
    monkeypatch.delenv("OS_TEST_FLAVOR", raising=False)
    monkeypatch.delenv("OS_TEST_IMAGES", raising=False)
    monkeypatch.delenv("OS_TEST_PROJECT_NAME", raising=False)

    pathlib.Path("spread.yaml").write_text(
        textwrap.dedent(
            """
            project: fetch-service
            backends:
              craft:
                type: craft
                systems:
                  - ubuntu-24.04:
                  - ubuntu-22.04
                  - ubuntu-20.04
            suites:
              tests/general/:
                summary: Just a test
            """
        )
    )
    state = models.PackState(
        artifacts=[models.PackedArtifact(name=None, path=pathlib.Path("foo"))]
    )
    testing_service.process_spread_yaml(new_dir / "processed", state)

    processed = pathlib.Path("processed").read_text()
    assert processed == textwrap.dedent(
        """\
        project: craft-test
        environment:
          SUDO_USER: ''
          SUDO_UID: ''
          LANG: C.UTF-8
          LANGUAGE: en
          PROJECT_PATH: /root/proj
          CRAFT_ARTIFACT: $PROJECT_PATH/foo
        backends:
          craft:
            type: adhoc
            allocate: ADDRESS $(./spread/.extension allocate lxd-vm)
            discard: ./spread/.extension discard lxd-vm
            systems:
            - ubuntu-24.04:
                workers: 1
            - ubuntu-22.04
            - ubuntu-20.04
            prepare: '"$PROJECT_PATH"/spread/.extension backend-prepare lxd-vm'
            restore: '"$PROJECT_PATH"/spread/.extension backend-restore lxd-vm'
            prepare-each: '"$PROJECT_PATH"/spread/.extension backend-prepare-each lxd-vm'
            restore-each: '"$PROJECT_PATH"/spread/.extension backend-restore-each lxd-vm'
        suites:
          tests/general/:
            summary: Just a test
            systems: []
        exclude:
        - .git
        - .tox
        path: /root/proj
        reroot: ..
        """
    )


def test_process_lp_test_spread_file(new_dir, monkeypatch, testing_service):
    monkeypatch.setenv("OS_AUTH_TYPE", "v3applicationcredential")
    monkeypatch.setenv("OS_AUTH_URL", "https://lp-test-endpoint:5000/v3")
    monkeypatch.setenv("OS_REGION_NAME", "prodstack7")
    monkeypatch.setenv("OS_TEST_FLAVOR", "cpu4-ram8-disk10")
    monkeypatch.setenv(
        "OS_TEST_IMAGES",
        '{"20.04": "ubuntu-focal-daily-amd64", '
        '"22.04": "ubuntu-jammy-daily-amd64", '
        '"24.04": "ubuntu-noble-daily-amd64"}',
    )
    monkeypatch.setenv("OS_TEST_PROJECT_NAME", "lp-test-project")
    pathlib.Path("spread.yaml").write_text(
        textwrap.dedent(
            """
            project: fetch-service
            backends:
              craft:
                type: craft
                systems:
                  - ubuntu-24.04:
                  - ubuntu-22.04
                  - ubuntu-20.04
            suites:
              tests/general/:
                summary: Just a test
            """
        )
    )
    state = models.PackState(
        artifacts=[models.PackedArtifact(name=None, path=pathlib.Path("foo"))]
    )
    testing_service.process_spread_yaml(new_dir / "processed", state)

    processed = pathlib.Path("processed").read_text()
    assert processed == textwrap.dedent(
        """\
        project: craft-test
        environment:
          SUDO_USER: ''
          SUDO_UID: ''
          LANG: C.UTF-8
          LANGUAGE: en
          PROJECT_PATH: /root/proj
          CRAFT_ARTIFACT: $PROJECT_PATH/foo
        backends:
          craft:
            type: openstack
            systems:
            - ubuntu-24.04:
                workers: 1
                image: ubuntu-noble-daily-amd64
            - ubuntu-22.04:
                workers: 1
                image: ubuntu-jammy-daily-amd64
            - ubuntu-20.04:
                workers: 1
                image: ubuntu-focal-daily-amd64
            prepare: '"$PROJECT_PATH"/spread/.extension backend-prepare lp-test'
            restore: '"$PROJECT_PATH"/spread/.extension backend-restore lp-test'
            prepare-each: '"$PROJECT_PATH"/spread/.extension backend-prepare-each lp-test'
            restore-each: '"$PROJECT_PATH"/spread/.extension backend-restore-each lp-test'
            endpoint: https://lp-test-endpoint:5000/v3
            account: user
            key: password
            location: lp-test-project/prodstack7
            plan: cpu4-ram8-disk10
            halt-timeout: 6h
        suites:
          tests/general/:
            summary: Just a test
            systems: []
        exclude:
        - .git
        - .tox
        path: /root/proj
        reroot: ..
        """
    )


def test_process_lp_test_spread_file_invalid_images(
    new_dir, monkeypatch, testing_service
):
    """A malformed OS_TEST_IMAGES value raises a CraftError."""
    monkeypatch.setenv("OS_AUTH_TYPE", "v3applicationcredential")
    monkeypatch.setenv("OS_AUTH_URL", "https://lp-test-endpoint:5000/v3")
    monkeypatch.setenv("OS_REGION_NAME", "prodstack7")
    monkeypatch.setenv("OS_TEST_FLAVOR", "cpu4-ram8-disk10")
    monkeypatch.setenv("OS_TEST_IMAGES", "not-json")
    monkeypatch.setenv("OS_TEST_PROJECT_NAME", "lp-test-project")
    pathlib.Path("spread.yaml").write_text(
        "backends:\n  craft:\n    systems: []\nsuites: {}\n"
    )
    state = models.PackState(
        artifacts=[models.PackedArtifact(name=None, path=pathlib.Path("foo"))]
    )

    with pytest.raises(CraftError, match="Invalid OS_TEST_IMAGES"):
        testing_service.process_spread_yaml(new_dir / "processed", state)


def test_process_lp_test_spread_file_non_dict_images(
    new_dir, monkeypatch, testing_service
):
    """A non-object OS_TEST_IMAGES value raises a CraftError."""
    monkeypatch.setenv("OS_AUTH_TYPE", "v3applicationcredential")
    monkeypatch.setenv("OS_AUTH_URL", "https://lp-test-endpoint:5000/v3")
    monkeypatch.setenv("OS_REGION_NAME", "prodstack7")
    monkeypatch.setenv("OS_TEST_FLAVOR", "cpu4-ram8-disk10")
    monkeypatch.setenv("OS_TEST_IMAGES", '["a", "b"]')
    monkeypatch.setenv("OS_TEST_PROJECT_NAME", "lp-test-project")
    pathlib.Path("spread.yaml").write_text(
        "backends:\n  craft:\n    systems: []\nsuites: {}\n"
    )
    state = models.PackState(
        artifacts=[models.PackedArtifact(name=None, path=pathlib.Path("foo"))]
    )

    with pytest.raises(CraftError, match="Invalid OS_TEST_IMAGES"):
        testing_service.process_spread_yaml(new_dir / "processed", state)


def test_process_lp_test_spread_file_missing_required_vars(
    new_dir, monkeypatch, testing_service
):
    """Missing OS_AUTH_URL or OS_TEST_FLAVOR raises a CraftError."""
    monkeypatch.setenv("OS_AUTH_TYPE", "v3applicationcredential")
    monkeypatch.setenv("OS_REGION_NAME", "prodstack7")
    monkeypatch.setenv("OS_TEST_PROJECT_NAME", "lp-test-project")
    monkeypatch.delenv("OS_AUTH_URL", raising=False)
    monkeypatch.delenv("OS_TEST_FLAVOR", raising=False)
    pathlib.Path("spread.yaml").write_text(
        "backends:\n  craft:\n    systems: []\nsuites: {}\n"
    )
    state = models.PackState(
        artifacts=[models.PackedArtifact(name=None, path=pathlib.Path("foo"))]
    )

    with pytest.raises(CraftError, match="Missing required environment"):
        testing_service.process_spread_yaml(new_dir / "processed", state)


def test_get_backend_type_requires_prodstack7_region(monkeypatch, testing_service):
    """The lp-test backend is only selected on prodstack7."""
    for var in ("OS_AUTH_TYPE", "OS_REGION_NAME", "OS_TEST_PROJECT_NAME"):
        monkeypatch.delenv(var, raising=False)

    assert testing_service._get_backend_type() == "lxd-vm"

    monkeypatch.setenv("OS_AUTH_TYPE", "v3applicationcredential")
    monkeypatch.setenv("OS_TEST_PROJECT_NAME", "lp-test-project")
    monkeypatch.setenv("OS_REGION_NAME", "other-region")

    assert testing_service._get_backend_type() == "lxd-vm"

    monkeypatch.setenv("OS_REGION_NAME", "prodstack7")

    assert testing_service._get_backend_type() == "lp-test"


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
