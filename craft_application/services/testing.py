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

import pathlib

from craft_cli import emit

from craft_application import models, util

from . import base


class TestingService(base.AppService):
    """Service class for testing a project."""

    def process_spread_yaml(self) -> None:
        """Process the spread configuration file.

        :param project_dir: The directory to initialise the project in.
        :param project_name: The name of the project.
        """
        emit.debug("Processing spread.yaml.")

        craft_backend = self._get_backend()

        with pathlib.Path("spread.yaml").open() as file:
            data = util.safe_yaml_load(file)

        simple = models.SimpleSpreadYaml.unmarshal(data)

        spread_yaml = models.SpreadYaml.from_simple(
            simple,
            craft_backend=craft_backend,
        )

        spread_yaml.to_yaml_file(pathlib.Path("spread/spread.yaml"))

    def _get_backend(self) -> models.SpreadBackend:
        name = "lxd-vm"

        return models.SpreadBackend(
            type="adhoc",
            allocate=f"ADDRESS $(./.extension allocate {name})",
            discard=f"./.extension discard {name}",
            prepare=f'"$PROJECT_PATH"/.extension backend-prepare {name}',
            restore=f'"$PROJECT_PATH"/.extension backend-restore {name}',
            prepare_each=f'"$PROJECT_PATH"/.extension backend-prepare-each {name}',
            restore_each=f'"$PROJECT_PATH"/.extension backend-restore-each {name}',
        )
