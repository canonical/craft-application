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
"""Tests for the lint command."""

from __future__ import annotations

import argparse
from typing import TYPE_CHECKING

import pytest
from craft_application.commands.lint import (
    LintCommand,
    _build_cli_ignore_config,
    _parse_ignore_rule,
)
from craft_application.lint import LintContext, LinterIssue, Severity, Stage
from craft_application.lint.base import AbstractLinter
from craft_application.services.linter import LinterService

if TYPE_CHECKING:
    from collections.abc import Iterator


@pytest.fixture
def restore_linter_registry() -> Iterator[None]:
    saved = LinterService._class_registry
    try:
        yield
    finally:
        LinterService._class_registry = saved


class _ErroringLinter(AbstractLinter):
    name = "unit.erroring"
    stage = Stage.PRE

    def run(self, ctx: LintContext):
        target = ctx.project_dir / "lint.txt"
        target.write_text("bad")
        yield LinterIssue(
            id="UNIT001",
            message="failed check",
            severity=Severity.ERROR,
            filename=str(target),
        )


@pytest.mark.usefixtures("restore_linter_registry")
def test_lint_command_outputs_issues(
    app_metadata,
    fake_services,
    fake_project,
    emitter,
):
    LinterService.register(_ErroringLinter)
    command = LintCommand({"app": app_metadata, "services": fake_services})

    project_service = fake_services.get("project")
    project_service.set(fake_project)  # type: ignore[reportAttributeAccessIssue]
    project_file = project_service.resolve_project_file_path()
    project_dir = project_file.parent
    project_dir.mkdir(parents=True, exist_ok=True)

    parsed_args = argparse.Namespace(
        stage=Stage.PRE.value,
        lint_ignores=[],
        lint_ignore_files=[],
    )

    command.run(parsed_args)

    assert emitter.assert_message("lint results:")
    assert emitter.assert_message("unit.erroring:")
    assert any(
        interaction.args[1].startswith("  - [ERROR] UNIT001: failed check (")
        for interaction in emitter.interactions
        if interaction.args and interaction.args[0] == "message"
    )
    assert emitter.assert_message(f"Errors found in {project_file.name}")


def test_build_cli_ignore_config() -> None:
    rules = [
        _parse_ignore_rule("dummy.pre:D001"),
        _parse_ignore_rule("dummy.pre:D002=*.foo"),
        _parse_ignore_rule("other:*"),
    ]
    config = _build_cli_ignore_config(rules)

    dummy_spec = config["dummy.pre"]
    assert isinstance(dummy_spec.ids, set)
    assert dummy_spec.ids == {"D001"}
    assert dummy_spec.by_filename == {"D002": {"*.foo"}}

    other_spec = config["other"]
    assert other_spec.ids == "*"
    assert other_spec.by_filename == {}
