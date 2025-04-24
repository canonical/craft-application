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

"""Service for testing a project."""

import os
import pathlib
import shlex
import shutil
import subprocess
import tempfile
from collections.abc import Collection

import craft_platforms
import distro
from craft_cli import CraftError, emit

from craft_application import models, util

from . import base


class TestingService(base.AppService):
    """Service class for testing a project."""

    __test__ = False  # Tell pytest this service is not a test class.

    def validate_tests(self, tests: Collection[pathlib.Path]) -> None:
        """Validate that each of the provided test names exists."""
        emit.debug("Checking that the specified test paths are valid")
        invalid_tests: list[str] = []
        for test in tests:
            if (test / "task.yaml").is_file():
                continue
            invalid_tests.append(str(test))
        if invalid_tests:
            invalid_tests_str = util.humanize_list(invalid_tests, "and")
            raise CraftError(
                f"Invalid test value(s): {invalid_tests_str}",
                resolution="Check the test paths and try again",
                logpath_report=False,
            )

    def test(
        self,
        project_path: pathlib.Path,
        *,
        tests: Collection[pathlib.Path] = (),
        shell: bool = False,
        shell_after: bool = False,
        debug: bool = False,
    ) -> None:
        """Run the full set of spread tests.

        This method is likely the all you need to call.

        :param project_path: the path to the project directory containing spread.yaml.
        """
        with tempfile.TemporaryDirectory(
            prefix=".craft-spread-",
            dir=project_path,
        ) as temp_dir:
            temp_dir_path = pathlib.Path(temp_dir)
            emit.trace(f"Temporary spread directory: {temp_dir_path}")
            temp_spread_file = temp_dir_path / "spread.yaml"
            self.process_spread_yaml(temp_spread_file)
            emit.trace(f"Temporary spread file:\n{temp_spread_file.read_text()}")
            self.run_spread(
                temp_dir_path,
                tests=tests,
                shell=shell,
                shell_after=shell_after,
                debug=debug,
            )

    def process_spread_yaml(self, dest: pathlib.Path) -> None:
        """Process the spread configuration file.

        :param dest: the output path for spread.yaml.
        """
        emit.debug("Processing spread.yaml.")
        spread_path = pathlib.Path("spread.yaml")
        if not spread_path.is_file():
            raise CraftError(
                "Could not find 'spread.yaml' in the current directory.",
                resolution="Ensure you are in the correct directory or create a spread.yaml file.",
                reportable=False,
                logpath_report=False,
                retcode=os.EX_CONFIG,
            )

        craft_backend = self._get_backend()

        with spread_path.open() as file:
            data = util.safe_yaml_load(file)

        simple = models.CraftSpreadYaml.unmarshal(data)

        spread_yaml = models.SpreadYaml.from_craft(
            simple,
            craft_backend=craft_backend,
        )

        emit.trace(f"Writing processed spread file to {dest}")
        spread_yaml.to_yaml_file(dest)

    def _get_spread_command(
        self,
        *,
        tests: Collection[pathlib.Path] = (),
        shell: bool = False,
        shell_after: bool = False,
        debug: bool = False,
    ) -> list[str]:
        """Get the full spread command to run."""
        cmd = [
            self._get_spread_executable(),
            "-v",
        ]
        if shell:
            cmd.append("-shell")
        if shell_after:
            cmd.append("-shell-after")
        if debug:
            cmd.append("-debug")

        system = self._get_system()
        backend_system_str = f"craft:{system}" if system else "craft"

        if tests:
            self.validate_tests(tests)
            cmd.extend(f"{backend_system_str}:{test}" for test in tests)
        else:
            cmd.append(f"{backend_system_str}:")

        emit.debug(f"Running spread as: {shlex.join(cmd)}")

        return cmd

    def run_spread(
        self,
        spread_dir: pathlib.Path,
        *,
        tests: Collection[pathlib.Path] = (),
        shell: bool = False,
        shell_after: bool = False,
        debug: bool = False,
    ) -> None:
        """Run spread on the processed project file.

        :param spread_dir: The working directory where spread should run.
        :param shell: Whether to pass the ``-shell`` option to spread.
        """
        emit.debug("Running spread tests.")
        spread_command = self._get_spread_command(
            tests=tests, shell=shell, shell_after=shell_after, debug=debug
        )

        try:
            with emit.open_stream("Running spread tests") as stream:
                subprocess.run(
                    spread_command,
                    check=True,
                    stdout=stream,
                    stderr=stream,
                    cwd=spread_dir,
                )
        except subprocess.CalledProcessError as exc:
            raise CraftError(
                "spread run failed",
                reportable=False,
                retcode=exc.returncode,
            )

    def _get_backend_type(self) -> str:
        return "ci" if os.environ.get("CI") else "lxd-vm"

    def _get_system(self) -> str:
        name = self._get_backend_type()

        if name == "ci":
            try:
                distro_base = craft_platforms.DistroBase.from_linux_distribution(
                    distro.LinuxDistribution()
                )
                system = f"{distro_base.distribution}-{distro_base.series}"
            except (CraftError, FileNotFoundError):
                system = ""
        else:
            system = ""

        return system

    def _get_backend(self) -> models.SpreadBackend:
        name = self._get_backend_type()

        return models.SpreadBackend(
            type="adhoc",
            # Allocate and discard occur on the host.
            allocate=f"ADDRESS $(./spread/.extension allocate {name})",
            discard=f"./spread/.extension discard {name}",
            # Each of these occur within the spread runner.
            prepare=f'"$PROJECT_PATH"/spread/.extension backend-prepare {name}',
            restore=f'"$PROJECT_PATH"/spread/.extension backend-restore {name}',
            prepare_each=f'"$PROJECT_PATH"/spread/.extension backend-prepare-each {name}',
            restore_each=f'"$PROJECT_PATH"/spread/.extension backend-restore-each {name}',
        )

    def _get_spread_executable(self) -> str:
        """Get the executable to run for spread.

        :returns: The spread command to use
        :raises: CraftError if spread cannot be found.
        """
        # Spread included in the application.
        if path := shutil.which("craft.spread"):
            return path
        raise CraftError(
            "Internal error: cannot find a 'craft.spread' executable.",
            details=f"'{self._app.name} test' needs 'craft.spread' to run.",
            resolution="This is likely a packaging bug that needs reporting.",
            retcode=os.EX_SOFTWARE,
        )
