# This file is part of craft-application.
#
# Copyright 2026 Canonical Ltd.
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
"""Tests for prune-instances command."""

import argparse

from craft_application.commands import PruneInstancesCommand


def test_prune_instances_run(app_metadata, mock_services):
    parsed_args = argparse.Namespace(
        all_providers=True,
        provider="lxd",
        include_templates=True,
    )
    command = PruneInstancesCommand({"app": app_metadata, "services": mock_services})
    command.run(parsed_args)

    mock_services.provider.prune_instances.assert_called_once_with(
        all_providers=True,
        provider_name="lxd",
        include_templates=True,
    )
