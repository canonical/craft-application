# This file is part of craft_application.
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
"""Testcraft-specific linters and linter service."""

from __future__ import annotations

import contextlib
import tarfile
import tempfile
from pathlib import Path
from typing import TYPE_CHECKING

from craft_application.lint import LintContext, LinterIssue, Severity, Stage
from craft_application.lint.base import AbstractLinter
from craft_application.services.linter import LinterService
from craft_application.util import yaml as yaml_util
from craft_cli import emit

from testcraft.application import TESTCRAFT

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

PROJECT_FILE = f"{TESTCRAFT.name}.yaml"


class MissingVersionLinter(AbstractLinter):
    """Warn when the project is missing the recommended version field."""

    name = "testcraft.missing_version"
    stage = Stage.PRE

    def run(self, ctx: LintContext) -> Iterable[LinterIssue]:
        """Check for the presence of the 'version' field in the project file."""
        project_file = ctx.project_dir / PROJECT_FILE
        if not project_file.exists():
            return

        data = yaml_util.safe_yaml_load(project_file.read_text())
        if not isinstance(data, dict):
            return

        if data.get("version"):
            return

        yield LinterIssue(
            id="TC001",
            message="project is missing the recommended 'version' field",
            severity=Severity.WARNING,
            filename=str(project_file),
        )


class EmptyArtifactLinter(AbstractLinter):
    """Error when packed artifacts contain only metadata.yaml."""

    name = "testcraft.empty_artifact"
    stage = Stage.POST

    def run(self, ctx: LintContext) -> Iterable[LinterIssue]:
        """Check for the presence of non-metadata files in the artifact directory."""
        for artifact_dir in ctx.artifact_dirs:
            if not artifact_dir.exists():
                continue

            non_metadata_entries = [
                entry
                for entry in artifact_dir.iterdir()
                if entry.name != "metadata.yaml" and not entry.name.startswith(".")
            ]
            if non_metadata_entries:
                continue

            yield LinterIssue(
                id="TC100",
                message="artifact is empty other than metadata.yaml",
                severity=Severity.ERROR,
                filename=str(artifact_dir / "metadata.yaml"),
            )


class TestcraftLinterService(LinterService):
    """Linter service that injects Testcraft's additional linters."""

    _EXTRA_LINTERS = {
        Stage.PRE: [MissingVersionLinter],
        Stage.POST: [EmptyArtifactLinter],
    }

    def pre_filter_linters(  # type: ignore[override]
        self,
        stage: Stage,
        ctx: LintContext,
        candidates: list[type[AbstractLinter]] | None = None,
    ) -> list[type[AbstractLinter]]:
        """Inject Testcraft's additional linters into the selected set."""
        selected = super().pre_filter_linters(stage, ctx, candidates)
        extras = self._EXTRA_LINTERS.get(stage, [])
        for extra in extras:
            if extra not in selected:
                selected.append(extra)
        return selected

    def run(  # type: ignore[override]
        self,
        stage: Stage,
        ctx: LintContext,
    ) -> Iterator[LinterIssue]:
        """Run linters, unpacking artifacts for post-stage checks when needed."""
        if stage == Stage.POST and not ctx.artifact_dirs:
            with contextlib.ExitStack() as stack:
                artifact_dirs = self._prepare_artifact_dirs(stack)
                if artifact_dirs:
                    ctx = LintContext(
                        project_dir=ctx.project_dir,
                        artifact_dirs=artifact_dirs,
                    )
                    yield from super().run(stage, ctx)
                    return
        yield from super().run(stage, ctx)

    def _prepare_artifact_dirs(
        self,
        stack: contextlib.ExitStack,
    ) -> list[Path]:
        """Extract the most recent packed artifacts for post-stage linting."""
        package = self._services.get("package")
        pack_state = package.read_state()

        artifacts: list[Path] = []
        if pack_state.artifact:
            artifacts.append(pack_state.artifact)
        if pack_state.resources:
            artifacts.extend(pack_state.resources.values())

        prepared: list[Path] = []
        for artifact in artifacts:
            if not artifact.exists():
                emit.debug(f"Skipping missing artifact {artifact}")
                continue
            if not tarfile.is_tarfile(artifact):
                emit.debug(f"Artifact {artifact} is not a tarball; skipping unpack")
                continue

            tmp_path = Path(
                stack.enter_context(
                    tempfile.TemporaryDirectory(prefix="testcraft-lint-")
                )
            )
            emit.debug(f"Extracting artifact {artifact} to {tmp_path}")
            with tarfile.open(artifact) as tar:
                try:
                    tar.extractall(path=tmp_path, filter="data")
                except TypeError:
                    tar.extractall(path=tmp_path)
            prepared.append(tmp_path)
        return prepared
