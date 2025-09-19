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
"""Orchestrates linter registration, ignore config and execution."""

from __future__ import annotations

import inspect
from collections.abc import Iterable, Iterator
from typing import TYPE_CHECKING, Any, cast

from craft_cli import emit

from craft_application import util
from craft_application.lint.types import (
    ExitCode,
    IgnoreConfig,
    IgnoreSpec,
    LintContext,
    LinterIssue,
    Severity,
    Stage,
    should_ignore,
)
from craft_application.services import base

if TYPE_CHECKING:
    from pathlib import Path

    from craft_application.application import AppMetadata
    from craft_application.lint.base import AbstractLinter
    from craft_application.services.service_factory import ServiceFactory


class LinterService(base.AppService):
    """Orchestrates linter registration, ignore config and execution."""

    _class_registry: dict[Stage, list[type[AbstractLinter]]] = {
        Stage.PRE: [],
        Stage.POST: [],
    }

    def __init__(self, app: AppMetadata, services: ServiceFactory) -> None:
        super().__init__(app, services)
        self._ignore_cfg: IgnoreConfig = {}
        self._issues: list[LinterIssue] = []

    @classmethod
    def register(cls, linter_cls: type[AbstractLinter]) -> None:
        """Register a linter class for use by the service."""
        if inspect.isabstract(linter_cls):
            return
        stage = getattr(linter_cls, "stage", None)
        name = getattr(linter_cls, "name", None)
        if not isinstance(stage, Stage) or not isinstance(name, str) or not name:
            raise ValueError(
                f"Invalid linter class {linter_cls!r}: missing/invalid name or stage"
            )
        emit.debug(f"Registering linter {name!r} for stage {stage.value}")
        cls._class_registry[stage].append(linter_cls)

    @classmethod
    def build_ignore_config(
        cls,
        project_dir: Path,
        cli_ignores: list[str] | None = None,
        cli_ignore_files: list[Path] | None = None,
    ) -> IgnoreConfig:
        """Merge ignore config from standard file(s) and CLI rules."""
        config: IgnoreConfig = {}
        file_cfg = cls._load_ignore_file(project_dir)
        if file_cfg:
            cls._merge_into(config, file_cfg)
        if cli_ignore_files:
            for extra in cli_ignore_files:
                if extra and extra.exists():
                    data = util.safe_yaml_load(extra.read_text())
                    if isinstance(data, dict):
                        cls._merge_into(
                            config,
                            cls._normalize_ignore_config(cast(dict[str, Any], data)),
                        )
        if cli_ignores:
            cls._merge_into(config, cls._parse_cli_ignores(cli_ignores))
        return config

    def load_ignore_config(
        self,
        project_dir: Path,
        cli_ignores: list[str] | None = None,
        cli_ignore_files: list[Path] | None = None,
    ) -> IgnoreConfig:
        """Load and cache ignore config, merging CLI rules if any."""
        self._ignore_cfg = self.__class__.build_ignore_config(
            project_dir, cli_ignores, cli_ignore_files
        )
        return self._ignore_cfg

    @staticmethod
    def _load_ignore_file(project_dir: Path) -> IgnoreConfig:
        """Load ignore config from a standard location in the project dir, if any."""
        candidates = [
            project_dir / "craft-lint.yaml",
            project_dir / ".craft-lint.yaml",
            project_dir / ".craft" / "lintignore.yaml",
        ]
        for p in candidates:
            if p.exists():
                emit.debug(f"Loading linter ignore config from {p}")
                data = util.safe_yaml_load(p.read_text())
                if not isinstance(data, dict):
                    emit.debug(
                        "Lint ignore config is not a mapping; ignoring this file."
                    )
                    return {}
                return LinterService._normalize_ignore_config(
                    cast(dict[str, Any], data)
                )
        return {}

    @staticmethod
    def _normalize_ignore_config(raw: dict[str, Any]) -> IgnoreConfig:
        """Normalize raw YAML data into IgnoreConfig structure."""
        cfg: IgnoreConfig = {}
        for linter_name, spec in raw.items():
            if not isinstance(spec, dict):
                continue
            spec_dict = cast(dict[str, Any], spec)
            ids_raw = cast(str | list[str] | set[str] | None, spec_dict.get("ids"))
            by_filename_raw = cast(
                dict[str, list[str] | set[str]] | None, spec_dict.get("by_filename")
            )

            if ids_raw == "*":
                norm_ids: str | set[str] = "*"
            else:
                norm_ids = set(cast(Iterable[str], ids_raw or []))

            norm_by_fname: dict[str, set[str]] = {}
            for issue_id, globs in (by_filename_raw or {}).items():
                norm_by_fname[str(issue_id)] = set(cast(Iterable[str], globs or []))
            cfg[str(linter_name)] = IgnoreSpec(ids=norm_ids, by_filename=norm_by_fname)
        return cfg

    @staticmethod
    def _parse_cli_ignores(rules: list[str]) -> IgnoreConfig:
        """Parse CLI rules like 'linter:id' or 'linter:id=glob' into IgnoreConfig."""
        result: IgnoreConfig = {}
        for rule in rules:
            if not rule:
                continue

            try:
                linter_name, remainder = rule.split(":", 1)
            except ValueError:
                continue

            if "=" in remainder:
                issue_id, glob = remainder.split("=", 1)
                spec = result.setdefault(
                    linter_name, IgnoreSpec(ids=set(), by_filename={})
                )

                spec.by_filename.setdefault(issue_id, set()).add(glob)
            else:
                issue_id = remainder
                spec = result.setdefault(
                    linter_name, IgnoreSpec(ids=set(), by_filename={})
                )
                if isinstance(spec.ids, set):
                    spec.ids.add(issue_id)
                else:
                    pass
        return result

    @staticmethod
    def _merge_into(base_cfg: IgnoreConfig, overlay: IgnoreConfig) -> None:
        """Merge overlay rules into base config, with overlay taking precedence."""
        for linter_name, over_spec in overlay.items():
            if linter_name not in base_cfg:
                base_cfg[linter_name] = IgnoreSpec(
                    ids=set() if over_spec.ids != "*" else "*",
                    by_filename={k: set(v) for k, v in over_spec.by_filename.items()},
                )
                if over_spec.ids == "*":
                    continue
                if isinstance(over_spec.ids, set):
                    base_cfg[linter_name].ids = set(over_spec.ids)
                continue
            base_spec = base_cfg[linter_name]

            if over_spec.ids == "*":
                base_spec.ids = "*"
                base_spec.by_filename.clear()
            elif isinstance(over_spec.ids, set):
                if base_spec.ids != "*":
                    if not isinstance(base_spec.ids, set):
                        base_spec.ids = set()
                    base_spec.ids.update(over_spec.ids)
            for issue_id, globs in over_spec.by_filename.items():
                base_spec.by_filename.setdefault(issue_id, set()).update(globs)

    def pre_filter_linters(
        self,
        stage: Stage,
        ctx: LintContext,  # noqa: ARG002 (reserved for future use)
        candidates: list[type[AbstractLinter]] | None = None,
    ) -> list[type[AbstractLinter]]:
        """App-specific selection hook."""
        registry = type(self)._class_registry  # noqa: SLF001
        return list(candidates or registry.get(stage, []))

    def post_filter_issues(
        self,
        linter: AbstractLinter,  # noqa: ARG002 (reserved for future use)
        issues: Iterable[LinterIssue],
        ctx: LintContext,  # noqa: ARG002 (reserved for future use)
    ) -> Iterator[LinterIssue]:
        """App-specific filtering hook."""
        yield from issues

    def run(
        self,
        stage: Stage,
        ctx: LintContext,
    ) -> Iterator[LinterIssue]:
        """Run linters for a stage, streaming non-suppressed issues."""
        self._issues.clear()
        registry = type(self)._class_registry  # noqa: SLF001
        selected = self.pre_filter_linters(stage, ctx, registry.get(stage, []))
        for cls in selected:
            linter = cls()
            raw_issues = linter.run(ctx)

            user_filtered = (
                issue
                for issue in raw_issues
                if not should_ignore(linter.name, issue, self._ignore_cfg)
            )
            filtered = self.post_filter_issues(linter, user_filtered, ctx)
            for issue in filtered:
                self._issues.append(issue)
                yield issue

    def summary(self) -> ExitCode:
        """Summarize results as an ExitCode based on highest severity."""
        if any(i.severity == Severity.ERROR for i in self._issues):
            return ExitCode.ERROR
        if any(i.severity == Severity.WARNING for i in self._issues):
            return ExitCode.WARN
        return ExitCode.OK

    @property
    def issues(self) -> list[LinterIssue]:
        """Return a copy of issues collected during the last run."""
        return list(self._issues)
