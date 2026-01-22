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

import argparse
from typing import TYPE_CHECKING, cast

from craft_cli import emit

from craft_application.commands import base
from craft_application.lint import IgnoreConfig, IgnoreSpec, LintContext, Stage

if TYPE_CHECKING:
    from pathlib import Path


def _parse_ignore_rule(value: str) -> tuple[str, str, str | None]:
    """Parse and validate a CLI ignore rule."""
    if ":" not in value:
        raise argparse.ArgumentTypeError(
            "Lint ignore rules must be in the form 'linter:id' or 'linter:id=glob'."
        )
    linter, remainder = value.split(":", 1)
    if not linter or not remainder:
        raise argparse.ArgumentTypeError(
            "Lint ignore rules must provide a linter name and issue id."
        )

    if "=" in remainder:
        issue, glob = remainder.split("=", 1)
        if not issue or not glob:
            raise argparse.ArgumentTypeError(
                "Lint ignore glob rules must be in the form 'linter:id=glob'."
            )
        return linter, issue, glob

    return linter, remainder, None


def _build_cli_ignore_config(rules: list[tuple[str, str, str | None]]) -> IgnoreConfig:
    """Convert parsed CLI ignore tuples into an IgnoreConfig."""
    config: IgnoreConfig = {}
    for linter, issue, glob in rules:
        spec = config.setdefault(linter, IgnoreSpec(ids=set(), by_filename={}))
        if issue == "*":
            spec.ids = "*"
            spec.by_filename.clear()
            continue
        if spec.ids == "*":
            continue
        if glob is None:
            if not isinstance(spec.ids, set):
                spec.ids = set()
            spec.ids.add(issue)
        else:
            spec.by_filename.setdefault(issue, set()).add(glob)
    return config


class LintCommand(base.AppCommand):
    """Run project linters."""

    name = "lint"
    help_msg = "Run linters against the project (pre) or artifacts (post)."
    overview = "Run linters against the project (pre) or artifacts (post)."

    def fill_parser(self, parser: argparse.ArgumentParser) -> None:
        """Add command-line arguments for lint configuration."""
        parser.add_argument(
            "--stage",
            choices=list(Stage),
            default=Stage.PRE,
            type=Stage,
            help="When to lint: 'pre' = source tree, 'post' = built artifacts.",
        )
        parser.add_argument(
            "--lint-ignore",
            action="append",
            dest="lint_ignores",
            type=_parse_ignore_rule,
            default=[],
            metavar="RULE",
            help=(
                "Ignore rule of the form 'linter:id' (ignore id everywhere) or "
                "'linter:id=glob' (ignore id when filename matches glob). May repeat."
            ),
        )

    def run(self, parsed_args: argparse.Namespace) -> int | None:
        """Execute lint for the requested stage and return the exit code."""
        services = self._services
        stage: Stage = parsed_args.stage

        # Resolve project dir
        project_service = services.get("project")
        project_file = project_service.resolve_project_file_path()
        project_dir: Path = project_file.parent
        filename = project_file.name
        if stage == Stage.POST and not project_service.is_configured:
            project_service.configure(platform=None, build_for=None)
            project_service.get()

        artifact_dirs: list[Path] = []
        if stage == Stage.POST:
            lifecycle = services.get("lifecycle")
            artifact_dirs = [lifecycle.prime_dir]

        ctx = LintContext(project_dir=project_dir, artifact_dirs=artifact_dirs)

        linter = services.get("linter")
        cli_ignore_rules = cast(
            list[tuple[str, str, str | None]], parsed_args.lint_ignores
        )
        cli_ignore_config = _build_cli_ignore_config(cli_ignore_rules)
        linter.load_ignore_config(
            project_dir=project_dir,
            cli_ignores=cli_ignore_config or None,
        )
        issues = list(linter.run(stage, ctx))

        if issues:
            emit.message("lint results:")
            for linter_name, linter_issues in linter.issues_by_linter.items():
                emit.message(f"{linter_name}:")
                for issue in linter_issues:
                    location = f" ({issue.filename})" if issue.filename else ""
                    emit.message(
                        f"  - [{issue.severity.name}] {issue.id}: {issue.message}{location}"
                    )

        highest = linter.get_highest_severity()
        if highest is None:
            emit.message(f"Linted {filename} successfully.")
            return 0
        if highest.name == "ERROR":
            emit.message(f"Errors found in {filename}")
            return 2

        emit.message(f"Possible issues found in {filename}")
        return 0
