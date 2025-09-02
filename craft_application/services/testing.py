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
from collections.abc import Iterable

import craft_platforms
import distro
from craft_cli import CraftError, emit

from craft_application import models, util

from . import base


class TestingService(base.AppService):
    """Service class for testing a project."""

    __test__ = False  # Tell pytest this service is not a test class.

    def test(
        self,
        project_path: pathlib.Path,
        pack_state: models.PackState,
        *,
        test_expressions: Iterable[str] = (),
        shell: bool = False,
        shell_after: bool = False,
        debug: bool = False,
    ) -> None:
        """Run the full set of spread tests.

        This method is likely the all you need to call.

        :param project_path: The path to the project directory containing spread.yaml.
        :param pack_state: An object containing the list of packed artifacts.
        :param test_expressions: A list of spread test expressions.
        :param shell: Whether to shell into the spread test instance.
        :param shell_after: Whether to shell into the spread test instance after the test runs.
        :param debug: Whether to shell into the spread test instance if the test fails.
        """
        with tempfile.TemporaryDirectory(
            prefix=".craft-spread-",
            dir=project_path,
        ) as temp_dir:
            temp_dir_path = pathlib.Path(temp_dir)
            emit.trace(f"Temporary spread directory: {temp_dir_path}")
            temp_spread_file = temp_dir_path / "spread.yaml"
            self.process_spread_yaml(temp_spread_file, pack_state)
            emit.trace(f"Temporary spread file:\n{temp_spread_file.read_text()}")
            self.run_spread(
                temp_dir_path,
                test_expressions=test_expressions,
                shell=shell,
                shell_after=shell_after,
                debug=debug,
            )

    def process_spread_yaml(
        self, dest: pathlib.Path, pack_state: models.PackState
    ) -> None:
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

        if not pack_state.artifact:
            raise CraftError(
                f"No {self._app.artifact_type} files to test.",
                resolution=f"Ensure that {self._app.artifact_type} files are generated before running the test.",
            )

        with spread_path.open() as file:
            data = util.safe_yaml_load(file)

        simple = models.CraftSpreadYaml.unmarshal(data)

        spread_yaml = models.SpreadYaml.from_craft(
            simple,
            craft_backend=craft_backend,
            artifact=pack_state.artifact,
            resources=pack_state.resources or {},
        )

        emit.trace(f"Writing processed spread file to {dest}")
        spread_yaml.to_yaml_file(dest)

    def _get_spread_command(
        self,
        *,
        test_expressions: Iterable[str] = (),
        shell: bool = False,
        shell_after: bool = False,
        debug: bool = False,
        cwd: pathlib.Path | None = None,
    ) -> list[str]:
        """Get the full spread command to run."""
        cmd = [self._get_spread_executable()]
        if shell:
            cmd.append("-shell")
        if shell_after:
            cmd.append("-shell-after")
        if debug:
            cmd.append("-debug")

        ci_system = self._get_ci_system()
        craft_prefix = f"craft:{ci_system}" if ci_system else "craft"
        spread_dir = cwd or pathlib.Path.cwd()

        if self._running_on_ci() and list(test_expressions) in (["craft"], ["craft:"]):
            # Set craft backend and host system to avoid job expansion.
            cmd.append(craft_prefix)
        elif test_expressions:
            if self._running_on_ci():
                # On CI, expand and filter jobs.
                test_expressions = self._filter_spread_jobs(
                    test_expressions,
                    prefix=craft_prefix,
                    cwd=spread_dir,
                )
                if not test_expressions:
                    raise CraftError(
                        "No matches for test the specified test filters.",
                        resolution="Ensure that test filters are correctly specified.",
                    )

            # User provided test expressions are passed to spread.
            cmd.extend(list(test_expressions))
        else:
            # Use the craft backend. If running on CI, also set the system.
            cmd.append(craft_prefix)

        emit.debug(f"Running spread as: {shlex.join(cmd)}")

        return cmd

    def _get_spread_list_command(
        self,
        test_expressions: Iterable[str],
    ) -> list[str]:
        """Get the full spread command to run."""
        spread_command = [self._get_spread_executable()]
        spread_command.append("-list")
        spread_command.extend(list(test_expressions))

        emit.debug(f"Running spread -list as: {shlex.join(spread_command)}")

        return spread_command

    def run_spread(
        self,
        spread_dir: pathlib.Path,
        *,
        test_expressions: Iterable[str] = (),
        shell: bool = False,
        shell_after: bool = False,
        debug: bool = False,
    ) -> None:
        """Run spread on the processed project file.

        :param spread_dir: The working directory where spread should run.
        :param test_expressions: A list of spread test expressions.
        :param shell: Whether to shell into the spread test instance.
        :param shell_after: Whether to shell into the spread test instance after the test runs.
        :param debug: Whether to shell into the spread test instance if the test fails.
        """
        emit.debug("Running spread tests.")
        spread_command = self._get_spread_command(
            test_expressions=test_expressions,
            shell=shell,
            shell_after=shell_after,
            debug=debug,
            cwd=spread_dir,
        )

        is_interactive = shell or shell_after or debug

        try:
            if is_interactive:
                # Don't pipe output into stream if spread runs in interactive
                # mode. This allows spread to run with proper terminal management
                # until we implement a protocol to pause the emitter and handle
                # terminal input and output inside an open_stream context. See
                # https://github.com/canonical/craft-cli/issues/347
                emit.debug("Pausing emitter for interactive spread shell")
                with emit.pause():
                    subprocess.run(spread_command, check=True, cwd=spread_dir)
            else:
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
                "Testing failed.",
                reportable=False,
                retcode=exc.returncode,
            )

    def _get_backend_type(self) -> str:
        return "ci" if os.environ.get("CI") else "lxd-vm"

    def _running_on_ci(self) -> bool:
        return self._get_backend_type() == "ci"

    def _get_ci_system(self) -> str:
        if self._running_on_ci():
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

    def _filter_spread_jobs(
        self,
        test_expressions: Iterable[str],
        *,
        prefix: str,
        cwd: pathlib.Path | None = None,
    ) -> list[str]:
        """Expand the list of spread jobs and filter by prefix.

        :param test_expressions: A list of spread test expressions.
        :param prefix: The prefix used to filter expressions.
        :return: A list of expressions starting with prefix.
        """
        spread_dir = cwd or pathlib.Path.cwd()
        spread_command = self._get_spread_list_command(test_expressions)
        try:
            proc = subprocess.run(
                spread_command,
                capture_output=True,
                text=True,
                check=True,
                cwd=spread_dir,
            )
        except subprocess.CalledProcessError as exc:
            emit.debug(f"error executing 'spread -list': {exc!s}")
            return []

        # Prevent matching partial elements
        prefix = prefix.rstrip(":") + ":"

        # Include jobs if it starts with craft:<host system>
        jobs = [line for line in proc.stdout.splitlines() if line.startswith(prefix)]
        emit.debug(f"filtered jobs: {jobs}")

        return jobs
