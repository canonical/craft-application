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
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Extension-related commands."""

from __future__ import annotations

import textwrap
from typing import TYPE_CHECKING

import craft_cli
from craft_cli import emit
from typing_extensions import override

from craft_application import util
from craft_application.commands import base
from craft_application.extensions import apply_extensions, registry

if TYPE_CHECKING:
    import argparse


def _format_table(headers: list[str], rows: list[list[str]]) -> str:
    """Format tabular data into an aligned text table."""
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(cell))
    header_line = "  ".join(
        f"{h:<{col_widths[i]}}" for i, h in enumerate(headers)
    ).rstrip()
    sep_line = "  ".join("-" * col_widths[i] for i in range(len(headers))).rstrip()
    data_lines = [
        "  ".join(f"{cell:<{col_widths[i]}}" for i, cell in enumerate(row)).rstrip()
        for row in rows
    ]
    return "\n".join([header_line, sep_line, *data_lines])


class ListExtensionsCommand(base.AppCommand):
    """List available extensions for all supported bases."""

    name = "list-extensions"
    help_msg = "List available extensions for all supported bases."
    overview = textwrap.dedent(
        """
        List available extensions and their corresponding bases.
        """
    )
    common = True

    @override
    def run(self, parsed_args: argparse.Namespace) -> None:
        """Print the list of available extensions and their bases."""
        headers = ["Extension name", "Supported bases"]
        rows: list[list[str]] = []
        for ext in registry.get_extensions():
            bases_str = ", ".join(ext["bases"]) if ext["bases"] else "all"
            rows.append([ext["name"], bases_str])

        emit.message(_format_table(headers, rows))


class ExtensionsCommand(ListExtensionsCommand):
    """Hidden alias for list-extensions."""

    name = "extensions"
    common = False
    hidden = True


class ExpandExtensionsCommand(base.AppCommand):
    """Expand extensions in the project file and display the output."""

    name = "expand-extensions"
    help_msg = "Expand extensions in the project file."
    overview = textwrap.dedent(
        """
        Extensions specified in the project file will be expanded and
        the resulting configuration printed to stdout.
        """
    )
    common = True

    @override
    def needs_project(self, parsed_args: argparse.Namespace) -> bool:
        return True

    @override
    def run(self, parsed_args: argparse.Namespace) -> None:
        """Print the project configuration with extensions expanded."""
        project_service = self._services.get("project")
        raw_project = project_service.get_raw()
        project_path = project_service.resolve_project_file_path()

        processed = apply_extensions(
            project_root=project_path.parent,
            yaml_data=raw_project,
            app_name=self._app.name,
        )
        emit.message(util.dump_yaml(processed))


def get_extensions_command_group() -> craft_cli.CommandGroup:
    """Return command group containing extension-related commands."""
    return craft_cli.CommandGroup(
        "Extensions",
        [ListExtensionsCommand, ExtensionsCommand, ExpandExtensionsCommand],
    )
