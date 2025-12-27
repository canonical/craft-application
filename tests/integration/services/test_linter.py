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
"""Integration tests for the LinterService."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

import pytest
from craft_application.lint import (
    ExitCode,
    LintContext,
    LinterIssue,
    Severity,
    Stage,
)
from craft_application.lint.base import AbstractLinter
from craft_application.services.linter import LinterService


@pytest.fixture
def restore_linter_registry() -> Iterator[None]:
    """Snapshot and restore the linter registry around a test."""
    saved = LinterService._class_registry
    try:
        yield
    finally:
        LinterService._class_registry = saved


@pytest.mark.usefixtures("restore_linter_registry")
def test_issue_then_ignore(
    fake_services,
    project_path,
    fake_project,
) -> None:
    class _FailingPreLinter(AbstractLinter):
        name = "integration.failing_pre"
        stage = Stage.PRE

        def run(self, ctx: LintContext):
            target = ctx.project_dir / "README.md"
            target.write_text("content")
            yield LinterIssue(
                id="INT001",
                message="integration failure",
                severity=Severity.ERROR,
                filename=str(target),
            )

    LinterService.register(_FailingPreLinter)

    project_service = fake_services.get("project")
    project_service.set(fake_project)  # type: ignore[reportAttributeAccessIssue]
    project_dir = project_service.resolve_project_file_path().parent
    project_dir.mkdir(parents=True, exist_ok=True)

    linter_service = fake_services.get("linter")
    ctx = LintContext(project_dir=project_dir, artifact_dirs=[])

    linter_service.load_ignore_config(project_dir=project_dir)
    issues = list(linter_service.run(Stage.PRE, ctx))
    assert [i.id for i in issues] == ["INT001"]
    assert linter_service.issues_by_linter == {_FailingPreLinter.name: issues}
    assert linter_service.summary() == ExitCode.ERROR

    ignore_file = project_dir / "craft-lint.yaml"
    ignore_file.write_text(f"{_FailingPreLinter.name}:\n  ids: ['INT001']\n")

    linter_service.load_ignore_config(project_dir=project_dir)
    rerun = list(linter_service.run(Stage.PRE, ctx))
    assert rerun == []
    assert linter_service.issues_by_linter == {}
    assert linter_service.summary() == ExitCode.OK
