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
"""Testcraft CLI command to run linters."""

from __future__ import annotations

import argparse
import tarfile
import tempfile
from pathlib import Path
from typing import cast

from craft_application.commands import base
from craft_application.lint import IgnoreConfig, IgnoreSpec, LintContext, Stage
from craft_cli import emit


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
    """Run Testcraft linters."""

    name = "lint"
    help_msg = "Run linters against the project or a packed artifact."
    overview = "Run linters against the project or a packed artifact."

    def fill_parser(self, parser: argparse.ArgumentParser) -> None:
        """Add command-line arguments for lint configuration."""
        parser.add_argument(
            "--post",
            type=Path,
            dest="post_artifact",
            metavar="ARTIFACT",
            help="Path to a packed artifact to lint with post-linters.",
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
        """Execute lint and return the exit code."""
        services = self._services

        project_service = services.get("project")
        project_file = project_service.resolve_project_file_path()
        project_dir = project_file.parent
        project_label = project_file.name

        stage = Stage.PRE
        artifact_dirs: list[Path] = []
        artifact_label = project_label

        if parsed_args.post_artifact is not None:
            stage = Stage.POST
            artifact = parsed_args.post_artifact
            if not artifact.exists():
                raise FileNotFoundError(f"Artifact {artifact} does not exist.")
            if not tarfile.is_tarfile(artifact):
                raise ValueError(f"Artifact {artifact} is not a supported tarball.")
            with tempfile.TemporaryDirectory(prefix="testcraft-lint-") as tmp_dir:
                tmp_path = Path(tmp_dir)
                with tarfile.open(artifact) as tar:
                    tar.extractall(path=tmp_path)
                artifact_dirs = [tmp_path]
                artifact_label = "artifacts"
                return self._run_stage(
                    stage,
                    project_dir,
                    artifact_dirs,
                    artifact_label,
                    cast(list[tuple[str, str, str | None]], parsed_args.lint_ignores),
                )

        return self._run_stage(
            stage,
            project_dir,
            artifact_dirs,
            artifact_label,
            cast(list[tuple[str, str, str | None]], parsed_args.lint_ignores),
        )

    def _run_stage(
        self,
        stage: Stage,
        project_dir: Path,
        artifact_dirs: list[Path],
        summary_label: str,
        cli_ignore_rules: list[tuple[str, str, str | None]],
    ) -> int:
        ctx = LintContext(project_dir=project_dir, artifact_dirs=artifact_dirs)
        linter = self._services.get("linter")

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
            emit.message(f"Linted {summary_label} successfully.")
            return 0
        if highest.name == "ERROR":
            emit.message(f"Errors found in {summary_label}")
            return 2

        emit.message(f"Possible issues found in {summary_label}")
        return 0
