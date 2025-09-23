# This file is part of craft-application.
#
# Copyright 2025 Canonical Ltd.
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
"""Public CLI command to run the linter service."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from craft_cli import emit

from craft_application.commands import base
from craft_application.lint.types import LintContext, Stage

if TYPE_CHECKING:
    import argparse


class LintCommand(base.AppCommand):
    """Run project linters."""

    name = "lint"
    help_msg = "Run linters against the project (pre) or artifacts (post)."
    overview = "Run linters against the project (pre) or artifacts (post)."

    def fill_parser(self, parser: argparse.ArgumentParser) -> None:
        """Add command-line arguments for lint configuration."""
        parser.add_argument(
            "--stage",
            choices=[Stage.PRE.value, Stage.POST.value],
            default=Stage.PRE.value,
            help="When to lint: 'pre' = source tree, 'post' = built artifacts.",
        )
        parser.add_argument(
            "--lint-ignore",
            action="append",
            dest="lint_ignores",
            default=[],
            metavar="RULE",
            help=(
                "Ignore rule of the form 'linter:id' (ignore id everywhere) or "
                "'linter:id=glob' (ignore id when filename matches glob). May repeat."
            ),
        )
        parser.add_argument(
            "--lint-ignore-file",
            action="append",
            type=Path,
            dest="lint_ignore_files",
            default=[],
            metavar="PATH",
            help=("Path to YAML ignore file. May repeat. CLI rules take precedence."),
        )

    def run(self, parsed_args: argparse.Namespace) -> int | None:
        """Execute lint for the requested stage and return the exit code."""
        services = self._services

        # Resolve project dir
        project_service = services.get("project")
        project_dir: Path = project_service.resolve_project_file_path().parent

        artifact_dirs: list[Path] = []
        if parsed_args.stage == Stage.POST.value:
            lifecycle = services.get("lifecycle")
            artifact_dirs = [lifecycle.prime_dir]

        ctx = LintContext(project_dir=project_dir, artifact_dirs=artifact_dirs)

        linter = services.get("linter")
        linter.load_ignore_config(
            project_dir=project_dir,
            cli_ignores=list(parsed_args.lint_ignores or []),
            cli_ignore_files=list(parsed_args.lint_ignore_files or []),
        )
        for _ in linter.run(Stage(parsed_args.stage), ctx):
            pass

        highest = linter.get_highest_severity()
        if highest is None:
            emit.message("lint: OK")
            return 0
        if highest.name == "ERROR":
            emit.message("lint: ERROR")
            return 2

        emit.message("lint: WARN")
        return 0
