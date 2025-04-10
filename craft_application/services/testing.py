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
import shutil
import subprocess
import tempfile

from craft_cli import CraftError, emit

from craft_application import models, util

from . import base


class TestingService(base.AppService):
    """Service class for testing a project."""

    __test__ = False  # Tell pytest this service is not a test class.

    def test(self, project_path: pathlib.Path) -> None:
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
            self.run_spread(temp_dir_path)

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

    def run_spread(self, spread_dir: pathlib.Path) -> None:
        """Run spread on the processed project file.

        :param spread_yaml: The path of the processed spread.yaml
        """
        emit.debug("Running spread tests.")
        try:
            with emit.open_stream("Running spread tests") as stream:
                subprocess.run(
                    [self._get_spread_executable(), "-v", "craft:"],
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

    def _get_backend(self) -> models.SpreadBackend:
        name = "ci" if os.environ.get("CI") else "lxd-vm"

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
