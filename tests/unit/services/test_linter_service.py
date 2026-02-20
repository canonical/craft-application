from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
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

if TYPE_CHECKING:
    from collections.abc import Iterator
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


def _make_ctx(tmp_path: Path, project) -> LintContext:
    return LintContext(project_dir=tmp_path, project=project, artifact_dirs=[])


@pytest.fixture(autouse=True)
def _seed_linter_registry(linter_registry_guard) -> Iterator[None]:
    """Reset class-level linter registry and seed the dummy linter per test."""
    with linter_registry_guard(_DummyPreLinter):
        yield


def test_run_warning(fake_services, fake_project, tmp_path: Path) -> None:
    project_service = fake_services.get("project")
    project_service.set(fake_project)  # type: ignore[reportAttributeAccessIssue]
    svc = fake_services.get("linter")
    ctx = _make_ctx(tmp_path, fake_project)

    issues = list(svc.run(Stage.PRE, ctx))
    assert len(issues) == 1
    assert issues[0].id == "D001"
    assert svc.issues_by_linter == {"dummy.pre": issues}
    assert svc.get_highest_severity() == Severity.WARNING
    assert svc.summary() == 0  # warnings do not cause non-zero exit


def test_ignore_by_id_cli(fake_services, fake_project, tmp_path: Path) -> None:
    project_service = fake_services.get("project")
    project_service.set(fake_project)  # type: ignore[reportAttributeAccessIssue]
    svc = fake_services.get("linter")
    ctx = _make_ctx(tmp_path, fake_project)

    cli_cfg: IgnoreConfig = {
        "dummy.pre": IgnoreSpec(ids={"D001"}, by_filename={}),
    }
    svc.load_ignore_config(project_dir=tmp_path, cli_ignores=cli_cfg)
    issues = list(svc.run(Stage.PRE, ctx))
    assert issues == []
    assert svc.issues_by_linter == {}
    assert int(svc.summary()) == 0  # OK


def test_ignore_by_glob_cli(fake_services, fake_project, tmp_path: Path) -> None:
    project_service = fake_services.get("project")
    project_service.set(fake_project)  # type: ignore[reportAttributeAccessIssue]
    svc = fake_services.get("linter")
    ctx = _make_ctx(tmp_path, fake_project)

    cli_cfg: IgnoreConfig = {
        "dummy.pre": IgnoreSpec(ids=set(), by_filename={"D001": {"*/README.*"}}),
    }
    svc.load_ignore_config(project_dir=tmp_path, cli_ignores=cli_cfg)
    issues = list(svc.run(Stage.PRE, ctx))
    assert issues == []
    assert svc.issues_by_linter == {}
    assert int(svc.summary()) == 0


def test_post_filter_hook_drops_issue(
    fake_services, fake_project, tmp_path: Path
) -> None:
    class Policy(LinterService):
        def post_filter_issues(self, linter: AbstractLinter, issues, ctx):  # type: ignore[override]
            return (i for i in issues if i.id != "D001")

    project_service = fake_services.get("project")
    project_service.set(fake_project)  # type: ignore[reportAttributeAccessIssue]
    svc = Policy(app=fake_services.app, services=fake_services)
    ctx = _make_ctx(tmp_path, fake_project)

    issues = list(svc.run(Stage.PRE, ctx))
    assert issues == []
    assert svc.issues_by_linter == {}
    assert int(svc.summary()) == 0


def test_normalize_ignore_config_handles_string_and_list_values() -> None:
    raw = {
        "dummy.pre": {
            "ids": "D001",
            "by_filename": {
                "D001": "*.md",
                "D002": ["*.txt", "*.rst"],
            },
        }
    }

    cfg = LinterService._normalize_ignore_config(raw)

    spec = cfg["dummy.pre"]
    assert spec.ids == {"D001"}
    assert spec.by_filename == {
        "D001": {"*.md"},
        "D002": {"*.txt", "*.rst"},
    }


def test_normalize_ignore_config_keeps_wildcard_ids() -> None:
    raw = {
        "dummy.pre": {
            "ids": "*",
            "by_filename": {
                "D001": "*.md",
            },
        }
    }

    cfg = LinterService._normalize_ignore_config(raw)

    spec = cfg["dummy.pre"]
    assert spec.ids == "*"
    assert spec.by_filename == {"D001": {"*.md"}}
