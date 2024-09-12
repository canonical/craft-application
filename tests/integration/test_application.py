# Copyright 2023-2024 Canonical Ltd.
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
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Integration tests for the Application."""
import argparse
import pathlib
import shutil
import textwrap

import craft_application
import craft_cli
import pytest
import pytest_check
from craft_application import models, secrets, util
from craft_application.util import yaml
from typing_extensions import override


class TestableApplication(craft_application.Application):
    """An application modified for integration tests.

    Modifications are:
    * Overrides the use of "/root/project" as project_dir when managed
    """

    def _pre_run(self, dispatcher: craft_cli.Dispatcher) -> None:
        super()._pre_run(dispatcher)
        if self.is_managed():
            self.project_dir = pathlib.Path.cwd()


@pytest.fixture
def create_app(app_metadata, fake_package_service_class):
    def _inner():
        # Create a factory without a project, to simulate a real application use
        # and force loading from disk.
        services = craft_application.ServiceFactory(
            app_metadata, PackageClass=fake_package_service_class
        )
        return TestableApplication(app_metadata, services)

    return _inner


@pytest.fixture
def app(create_app):
    return create_app()


BASIC_USAGE = """\
Usage:
    testcraft [help] <command>

Summary:    A fake app for testing craft-application

Global options:
       -h, --help:  Show this help message and exit
    -v, --verbose:  Show debug information and be more verbose
      -q, --quiet:  Only show warnings and errors, not progress
      --verbosity:  Set the verbosity level to 'quiet', 'brief',
                    'verbose', 'debug' or 'trace'
    -V, --version:  Show the application version and exit

Starter commands:
          version:  Show the application version and exit

Commands can be classified as follows:
        Lifecycle:  build, clean, pack, prime, pull, stage
            Other:  version

For more information about a command, run 'testcraft help <command>'.
For a summary of all commands, run 'testcraft help --all'.

"""
INVALID_COMMAND = """\
Usage: testcraft [options] command [args]...
Try 'testcraft -h' for help.

Error: no such command 'non-command'

"""
VERSION_INFO = "testcraft 3.14159\n"
TEST_DATA_DIR = pathlib.Path(__file__).parent / "data"
VALID_PROJECTS_DIR = TEST_DATA_DIR / "valid_projects"
INVALID_PROJECTS_DIR = TEST_DATA_DIR / "invalid_projects"


@pytest.mark.parametrize(
    ("argv", "stdout", "stderr", "exit_code"),
    [
        pytest.param(["help"], "", BASIC_USAGE, 0, id="help"),
        pytest.param(["--help"], "", BASIC_USAGE, 0, id="--help"),
        pytest.param(["-h"], "", BASIC_USAGE, 0, id="-h"),
        pytest.param(["--version"], VERSION_INFO, "", 0, id="--version"),
        pytest.param(["-V"], VERSION_INFO, "", 0, id="-V"),
        pytest.param(["-q", "--version"], "", "", 0, id="-q--version"),
        pytest.param(
            ["--invalid-parameter"], "", BASIC_USAGE, 64, id="--invalid-parameter"
        ),
        pytest.param(["non-command"], "", INVALID_COMMAND, 64, id="non-command"),
    ],
)
def test_special_inputs(capsys, monkeypatch, app, argv, stdout, stderr, exit_code):
    monkeypatch.setenv("CRAFT_DEBUG", "1")
    monkeypatch.setattr("sys.argv", ["testcraft", *argv])

    with pytest.raises(SystemExit) as exc_info:
        app.run()

    pytest_check.equal(exc_info.value.code, exit_code, "exit code incorrect")

    captured = capsys.readouterr()

    pytest_check.equal(captured.out, stdout, "stdout does not match")
    pytest_check.equal(captured.err, stderr, "stderr does not match")


@pytest.mark.usefixtures("pretend_jammy")
@pytest.mark.parametrize("project", (d.name for d in VALID_PROJECTS_DIR.iterdir()))
def test_project_managed(capsys, monkeypatch, tmp_path, project, create_app):
    monkeypatch.setenv("CRAFT_DEBUG", "1")
    monkeypatch.setenv("CRAFT_MANAGED_MODE", "1")
    monkeypatch.setattr("sys.argv", ["testcraft", "pack"])
    monkeypatch.chdir(tmp_path)
    shutil.copytree(VALID_PROJECTS_DIR / project, tmp_path, dirs_exist_ok=True)

    app = create_app()
    app._work_dir = tmp_path

    app.run()

    assert (tmp_path / "package_1.0.tar.zst").exists()
    captured = capsys.readouterr()
    assert (
        captured.err.splitlines()[-1]
        == (VALID_PROJECTS_DIR / project / "stderr").read_text()
    )


@pytest.mark.usefixtures("full_build_plan", "pretend_jammy")
@pytest.mark.parametrize("project", (d.name for d in VALID_PROJECTS_DIR.iterdir()))
def test_project_destructive(
    capsys,
    monkeypatch,
    tmp_path,
    project,
    create_app,
):
    monkeypatch.chdir(tmp_path)
    shutil.copytree(VALID_PROJECTS_DIR / project, tmp_path, dirs_exist_ok=True)

    build_for = util.get_host_architecture()
    release = util.get_host_base().version
    platform = f"ubuntu-{release}-{build_for}"

    # Run pack in destructive mode
    monkeypatch.setattr(
        "sys.argv",
        ["testcraft", "pack", "--destructive-mode", "--platform", platform],
    )
    app = create_app()
    app.run()

    assert (tmp_path / "package_1.0.tar.zst").exists()
    captured = capsys.readouterr()
    assert (
        captured.err.splitlines()[-1]
        == (VALID_PROJECTS_DIR / project / "stderr").read_text()
    )

    for dirname in ("parts", "stage", "prime"):
        assert (tmp_path / dirname).is_dir()

    # Now run clean in destructive mode
    monkeypatch.setattr("sys.argv", ["testcraft", "clean", "--destructive-mode"])
    app = create_app()
    app.run()

    for dirname in ("parts", "stage", "prime"):
        assert not (tmp_path / dirname).is_dir()


def test_version(capsys, monkeypatch, app):
    monkeypatch.setattr("sys.argv", ["testcraft", "version"])

    app.run()

    captured = capsys.readouterr()
    assert captured.out == "testcraft 3.14159\n"


@pytest.mark.usefixtures("emitter")
def test_non_lifecycle_command_does_not_require_project(monkeypatch, app):
    """Run a command without having a project instance shall not fail."""
    monkeypatch.setattr("sys.argv", ["testcraft", "nothing"])

    class NothingCommand(craft_cli.BaseCommand):
        name = "nothing"
        help_msg = "none"
        overview = "nothing to see here"

        @override
        def run(self, parsed_args: argparse.Namespace) -> None:
            craft_cli.emit.message(f"Nothing {parsed_args!r}")

    app.add_command_group("Nothing", [NothingCommand])
    app.run()


@pytest.mark.parametrize("cmd", ["clean", "pull", "build", "stage", "prime", "pack"])
def test_run_always_load_project(capsys, monkeypatch, app, cmd):
    """Run a lifecycle command without having a project shall fail."""
    monkeypatch.setenv("CRAFT_DEBUG", "1")
    monkeypatch.setattr("sys.argv", ["testcraft", cmd])

    assert app.run() == 66  # noqa: PLR2004

    captured = capsys.readouterr()
    assert "'testcraft.yaml' not found" in captured.err


@pytest.mark.parametrize("help_param", ["-h", "--help"])
@pytest.mark.parametrize(
    "cmd", ["clean", "pull", "build", "stage", "prime", "pack", "version"]
)
def test_get_command_help(monkeypatch, emitter, capsys, app, cmd, help_param):
    monkeypatch.setattr("sys.argv", ["testcraft", cmd, help_param])

    with pytest.raises(SystemExit) as exit_info:
        app.run()

    assert exit_info.value.code == 0

    # Ensure the command got help set to true.
    emitter.assert_trace(".+'help': True.+", regex=True)

    stdout, stderr = capsys.readouterr()

    assert f"testcraft {cmd} [options]" in stderr


def test_invalid_command_argument(monkeypatch, capsys, app):
    """Test help output when passing an invalid argument to a command."""
    monkeypatch.setattr("sys.argv", ["testcraft", "pack", "--invalid-argument"])

    return_code = app.run()

    assert return_code == 64  # noqa: PLR2004 (Magic number used in comparison)

    expected_stderr = textwrap.dedent(
        """\
        Usage: testcraft [options] command [args]...
        Try 'testcraft pack -h' for help.

        Error: unrecognized arguments: --invalid-argument

    """
    )

    stdout, stderr = capsys.readouterr()
    assert stderr == expected_stderr


@pytest.mark.parametrize(
    "arguments",
    [
        [],
        ["--build-for", "s390x"],
        ["--platform", "my-platform"],
    ],
)
def test_global_environment(
    arguments,
    create_app,
    mocker,
    monkeypatch,
    tmp_path,
):
    """Test that the global environment is correctly populated during the build process."""
    monkeypatch.chdir(tmp_path)
    shutil.copytree(VALID_PROJECTS_DIR / "environment", tmp_path, dirs_exist_ok=True)

    # a build plan that builds for s390x (a cross-compiling scenario unless on s390x)
    mocker.patch.object(
        models.BuildPlanner,
        "get_build_plan",
        return_value=[
            models.BuildInfo(
                platform="my-platform",
                build_on=util.get_host_architecture(),
                build_for="s390x",
                base=util.get_host_base(),
            ),
        ],
    )

    # Run in destructive mode
    monkeypatch.setattr(
        "sys.argv", ["testcraft", "prime", "--destructive-mode", *arguments]
    )
    app = create_app()
    app.run()

    # The project's build step stages a "variables.yaml" file containing the values of
    # variables taken from the global environment.
    variables_yaml = tmp_path / "stage/variables.yaml"
    assert variables_yaml.is_file()
    with variables_yaml.open() as file:
        variables = yaml.safe_yaml_load(file)

    assert variables["project_name"] == "environment-project"
    assert variables["project_dir"] == str(tmp_path)
    assert variables["project_version"] == "1.0"
    assert variables["arch_build_for"] == "s390x"
    assert variables["arch_triplet_build_for"] == "s390x-linux-gnu"
    assert variables["arch_build_on"] == "amd64"
    # craft-application doesn't have utility for getting arch triplets
    assert variables["arch_triplet_build_on"].startswith(
        util.convert_architecture_deb_to_platform(util.get_host_architecture())
    )


@pytest.fixture
def setup_secrets_project(create_app, monkeypatch, tmp_path):
    """Test the use of build secrets in destructive mode."""

    def _inner(*, destructive_mode: bool):
        monkeypatch.setenv("CRAFT_DEBUG", "1")
        monkeypatch.chdir(tmp_path)
        shutil.copytree(TEST_DATA_DIR / "build-secrets", tmp_path, dirs_exist_ok=True)

        argv = ["testcraft", "prime", "-v"]
        if destructive_mode:
            # Run in destructive mode
            argv.append("--destructive-mode")

        monkeypatch.setattr("sys.argv", argv)

        return create_app()

    return _inner


@pytest.fixture
def check_secrets_output(tmp_path, capsys):
    def _inner():
        prime_dir = tmp_path / "prime"
        assert (prime_dir / "source-file.txt").read_text().strip() == "A source file"
        assert (prime_dir / "build-file.txt").read_text().strip() == "my-secret"

        # Check that the "secrets" were masked in console output and the logfile
        _, stderr = capsys.readouterr()
        log_contents = craft_cli.emit._log_filepath.read_text()

        for target in (stderr, log_contents):
            assert "Dumping SECRET_VAR: my-secret" not in target
            assert "Dumping SECRET_VAR: *****" in target

    return _inner


@pytest.mark.usefixtures("pretend_jammy")
@pytest.mark.enable_features("build_secrets")
def test_build_secrets_destructive(
    monkeypatch, setup_secrets_project, check_secrets_output
):
    """Test the use of build secrets in destructive mode."""
    app = setup_secrets_project(destructive_mode=True)

    # Set the environment variables that the project needs
    monkeypatch.setenv("HOST_SOURCE_FOLDER", "secret-source")
    monkeypatch.setenv("HOST_SECRET_VAR", "my-secret")

    app.run()

    check_secrets_output()


@pytest.mark.usefixtures("pretend_jammy")
@pytest.mark.enable_features("build_secrets")
def test_build_secrets_managed(
    monkeypatch, tmp_path, setup_secrets_project, check_secrets_output
):
    """Test the use of build secrets in managed mode."""
    app = setup_secrets_project(destructive_mode=False)

    monkeypatch.setenv("CRAFT_MANAGED_MODE", "1")
    assert app.is_managed()
    app._work_dir = tmp_path

    # Before running the application, configure its environment "as if" the host app
    # had placed the secrets there.
    commands = {
        "echo ${HOST_SOURCE_FOLDER}": "secret-source",
        "echo ${HOST_SECRET_VAR}": "my-secret",
    }
    encoded = secrets._encode_commands(commands)
    monkeypatch.setenv("CRAFT_SECRETS", encoded["CRAFT_SECRETS"])

    app.run()

    check_secrets_output()


@pytest.mark.usefixtures("pretend_jammy")
def test_lifecycle_error_logging(monkeypatch, tmp_path, create_app):
    monkeypatch.chdir(tmp_path)
    shutil.copytree(INVALID_PROJECTS_DIR / "build-error", tmp_path, dirs_exist_ok=True)

    monkeypatch.setattr("sys.argv", ["testcraft", "pack", "--destructive-mode"])
    app = create_app()
    app.run()

    log_contents = craft_cli.emit._log_filepath.read_text()

    # Make sure there's a traceback
    assert "Traceback (most recent call last):" in log_contents

    # Make sure it's identified as the correct error type
    parts_message = "craft_parts.errors.ScriptletRunError: 'override-build' in part 'my-part' failed"
    assert parts_message in log_contents


@pytest.mark.usefixtures("pretend_jammy", "emitter")
def test_runtime_error_logging(monkeypatch, tmp_path, create_app, mocker):
    monkeypatch.chdir(tmp_path)
    shutil.copytree(INVALID_PROJECTS_DIR / "build-error", tmp_path, dirs_exist_ok=True)

    # Pretend a random piece of code in the LifecycleService raises a RuntimeError.
    runtime_error = RuntimeError("An unexpected error")
    mocker.patch(
        "craft_application.services.lifecycle._get_parts_action_message",
        side_effect=runtime_error,
    )

    monkeypatch.setattr("sys.argv", ["testcraft", "pack", "--destructive-mode"])
    app = create_app()

    app.run()

    log_contents = craft_cli.emit._log_filepath.read_text()

    # Make sure there's a traceback
    assert "Traceback (most recent call last):" in log_contents

    # Make sure it's identified as the correct error type
    parts_message = "Parts processing internal error: An unexpected error"
    assert parts_message in log_contents
