from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from craft_application.application import AppMetadata
from craft_application.lint import (
    IgnoreConfig,
    IgnoreSpec,
    LintContext,
    LinterIssue,
    Severity,
    Stage,
)
from craft_application.lint.base import AbstractLinter
from craft_application.services.linter import LinterService
from craft_application.services.service_factory import ServiceFactory

if TYPE_CHECKING:
    from pathlib import Path


class _DummyPreLinter(AbstractLinter):
    name = "dummy.pre"
    stage = Stage.PRE

    def run(self, ctx: LintContext):
        yield LinterIssue(
            id="D001",
            message="dummy warning",
            severity=Severity.WARNING,
            filename=str(ctx.project_dir / "README.md"),
        )


def _make_ctx(tmp_path: Path) -> LintContext:
    return LintContext(project_dir=tmp_path, artifact_dirs=[])


@pytest.fixture(autouse=True)
def _reset_linter_registry() -> None:
    """Clear class-level linter registry before each test to avoid leakage."""
    for registry in LinterService._class_registry.values():
        registry.clear()


def test_register_and_run_warning(tmp_path: Path) -> None:
    LinterService.register(_DummyPreLinter)
    app = AppMetadata(name="craft_application")
    factory = ServiceFactory(app)
    svc = LinterService(app=app, services=factory)
    ctx = _make_ctx(tmp_path)

    issues = list(svc.run(Stage.PRE, ctx))
    assert len(issues) == 1
    assert issues[0].id == "D001"
    assert svc.issues_by_linter == {"dummy.pre": issues}
    assert svc.get_highest_severity() == Severity.WARNING
    assert svc.summary() == 0  # warnings do not cause non-zero exit


def test_ignore_by_id_cli(tmp_path: Path) -> None:
    app = AppMetadata(name="craft_application")
    factory = ServiceFactory(app)
    svc = LinterService(app=app, services=factory)
    ctx = _make_ctx(tmp_path)

    cli_cfg: IgnoreConfig = {
        "dummy.pre": IgnoreSpec(ids={"D001"}, by_filename={}),
    }
    svc.load_ignore_config(project_dir=tmp_path, cli_ignores=cli_cfg)
    issues = list(svc.run(Stage.PRE, ctx))
    assert issues == []
    assert svc.issues_by_linter == {}
    assert int(svc.summary()) == 0  # OK


def test_ignore_by_glob_yaml(tmp_path: Path) -> None:
    yaml = tmp_path / "craft-lint.yaml"
    yaml.write_text(
        """
dummy.pre:
  by_filename:
    D001: ["*/README.*"]
"""
    )

    app = AppMetadata(name="craft_application")
    factory = ServiceFactory(app)
    svc = LinterService(app=app, services=factory)
    ctx = _make_ctx(tmp_path)

    svc.load_ignore_config(project_dir=tmp_path)
    issues = list(svc.run(Stage.PRE, ctx))
    assert issues == []
    assert svc.issues_by_linter == {}
    assert int(svc.summary()) == 0


def test_post_filter_hook_drops_issue(tmp_path: Path) -> None:
    class Policy(LinterService):
        def post_filter_issues(self, linter: AbstractLinter, issues, ctx):  # type: ignore[override]
            return (i for i in issues if i.id != "D001")

    app = AppMetadata(name="craft_application")
    factory = ServiceFactory(app)
    svc = Policy(app=app, services=factory)
    ctx = _make_ctx(tmp_path)

    issues = list(svc.run(Stage.PRE, ctx))
    assert issues == []
    assert svc.issues_by_linter == {}
    assert int(svc.summary()) == 0
