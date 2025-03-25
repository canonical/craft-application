#  This file is part of craft-application.
#
#  Copyright 2024 Canonical Ltd.
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

import atexit
import os
import pathlib
import shutil
import subprocess

from craft_cli import CraftError, emit

from craft_application import models, util

from . import base


class TestingService(base.AppService):
    """Service class for testing a project."""

    def process_spread_yaml(self, dest: pathlib.Path) -> None:
        """Process the spread configuration file.

        :param project_dir: The directory to initialise the project in.
        :param project_name: The name of the project.
        """
        emit.debug("Processing spread.yaml.")
        # For now we need to modify the spread.yaml file in-place.
        # See: https://github.com/canonical/spread/issues/225
        _ = dest
        spread_path = pathlib.Path("spread.yaml")
        spread_backup = spread_path.with_suffix(".yaml~")

        craft_backend = self._get_backend()

        with spread_path.open() as file:
            data = util.safe_yaml_load(file)

        shutil.move(spread_path, spread_backup)

        atexit.register(shutil.move, spread_backup, spread_path)

        simple = models.CraftSpreadYaml.unmarshal(data)

        spread_yaml = models.SpreadYaml.from_craft(
            simple,
            craft_backend=craft_backend,
        )

        spread_yaml.to_yaml_file(spread_path)

    def run_spread(self, project_path: pathlib.Path) -> None:
        """Run spread on the processed project file.

        :param project_path: The processed project file.
        """
        try:
            with emit.pause():
                subprocess.run(
                    ["spread", "-v", "craft:"],
                    check=True,
                    env=os.environ | {"SPREAD_PROJECT_FILE": project_path.as_posix()},
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
            allocate=f"ADDRESS $(./spread/.extension allocate {name})",
            discard=f"./spread/.extension discard {name}",
            prepare=f'"$PROJECT_PATH"/spread/.extension backend-prepare {name}',
            restore=f'"$PROJECT_PATH"/spread/.extension backend-restore {name}',
            prepare_each=f'"$PROJECT_PATH"/spread/.extension backend-prepare-each {name}',
            restore_each=f'"$PROJECT_PATH"/spread/.extension backend-restore-each {name}',
        )
