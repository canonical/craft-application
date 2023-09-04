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
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Integration tests for the Application."""
import argparse
import pathlib
import shutil

import craft_application
import craft_cli
import pytest
import pytest_check
from overrides import override


@pytest.fixture()
def app(app_metadata, fake_project, fake_package_service_class):
    services = craft_application.ServiceFactory(
        app_metadata, project=fake_project, PackageClass=fake_package_service_class
    )
    return craft_application.Application(app_metadata, services)


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
        (["help"], "", BASIC_USAGE, 0),
        (["--help"], "", BASIC_USAGE, 0),
        (["-h"], "", BASIC_USAGE, 0),
        (["--version"], VERSION_INFO, "", 0),
        (["-V"], VERSION_INFO, "", 0),
        (["-q", "--version"], VERSION_INFO, "", 0),
        (["--invalid-parameter"], "", BASIC_USAGE, 64),
        (["non-command"], "", INVALID_COMMAND, 64),
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


@pytest.mark.parametrize("project", (d.name for d in VALID_PROJECTS_DIR.iterdir()))
def test_project_managed(capsys, monkeypatch, tmp_path, project, app):
    monkeypatch.setenv("CRAFT_DEBUG", "1")
    monkeypatch.setenv("CRAFT_MANAGED_MODE", "1")
    monkeypatch.setattr("sys.argv", ["testcraft", "pack"])
    monkeypatch.chdir(tmp_path)
    shutil.copytree(VALID_PROJECTS_DIR / project, tmp_path, dirs_exist_ok=True)
    app._work_dir = tmp_path

    app.run()

    assert (tmp_path / "package.tar.zst").exists()
    captured = capsys.readouterr()
    assert captured.out == (VALID_PROJECTS_DIR / project / "stdout").read_text()


def test_version(capsys, monkeypatch, app):
    monkeypatch.setenv("CRAFT_DEBUG", "1")
    monkeypatch.setenv("CRAFT_MANAGED_MODE", "1")
    monkeypatch.setattr("sys.argv", ["testcraft", "version"])

    app.run()

    captured = capsys.readouterr()
    assert captured.out == "testcraft 3.14159\n"


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
