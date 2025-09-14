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
"""Types and helpers for the linter service.

Note: this module name intentionally overlaps with the stdlib ``types`` module.
We only import it within the package; to avoid confusion with external imports,
downstream users should prefer explicit imports from ``craft_application.lint``.
"""

from __future__ import annotations

# ruff: noqa: A005  # module name shadows stdlib 'types'
from dataclasses import dataclass
from enum import Enum
from fnmatch import fnmatch
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from pathlib import Path


class Stage(str, Enum):
    """Lifecycle stage for linting."""

    PRE = "pre"
    POST = "post"


class Severity(str, Enum):
    """Severity level for linter issues."""

    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class ExitCode(int, Enum):
    """Exit codes summarising lint results."""

    OK = 0
    WARN = 1
    ERROR = 2


@dataclass(frozen=True, slots=True)
class LintContext:
    """Stage-agnostic environment for linters.

    - project_dir: the source tree on disk
    - artifact_dirs: list of directories with built artifacts (may be empty in pre-stage)
    """

    project_dir: Path
    artifact_dirs: list[Path]


@dataclass(frozen=True, slots=True)
class LinterIssue:
    """Single issue reported by a linter."""

    id: str
    message: str
    severity: Severity
    filename: str
    url: str = ""


@dataclass(slots=True)
class IgnoreSpec:
    """Suppression rules for one linter.

    - ids: "*" to ignore every issue, or a set of issue ids
    - by_filename: map of issue id -> set of filename globs
    """

    ids: str | set[str]
    by_filename: dict[str, set[str]]


# Map of linter.name -> IgnoreSpec
IgnoreConfig = dict[str, IgnoreSpec]


def should_ignore(linter_name: str, issue: LinterIssue, cfg: IgnoreConfig) -> bool:
    """Return True when `issue` is covered by the user's ignore rules.

    Uses issue id and optional shell-style filename globs per the approved design.
    """
    spec = cfg.get(linter_name)
    if not spec:
        return False
    if spec.ids == "*":
        return True
    if isinstance(spec.ids, set) and issue.id in spec.ids:
        return True
    globs = spec.by_filename.get(issue.id, set()) or set()
    return any(fnmatch(issue.filename, g) for g in globs)
