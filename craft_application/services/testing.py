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

import os
import pathlib
import subprocess

from craft_cli import emit

from craft_application import models, util

from . import base


class TestingService(base.AppService):
    """Service class for testing a project."""

    def process_spread_yaml(self, destdir: pathlib.Path) -> None:
        """Process the spread configuration file.

        :param project_dir: The directory to initialise the project in.
        :param project_name: The name of the project.
        """
        emit.debug("Processing spread.yaml.")

        craft_backend = self._get_backend()

        with pathlib.Path("spread.yaml").open() as file:
            data = util.safe_yaml_load(file)

        simple = models.CraftSpreadYaml.unmarshal(data)

        spread_yaml = models.SpreadYaml.from_craft(
            simple,
            craft_backend=craft_backend,
        )

        spread_yaml.to_yaml_file(destdir / "spread.yaml")

    def run_spread(self, project_path: pathlib.Path) -> None:
        """Run spread on the processed project file.

        :param project_path: The processed project file.
        """
        with emit.pause():
            os.environ["SPREAD_PROJECT_FILE"] = str(project_path)
            subprocess.run(
                ["spread", "craft:"],
                cwd=project_path,
                check=True,
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
