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
"""Linter framework public API surface."""

from __future__ import annotations

from .types import (
    ExitCode,
    IgnoreConfig,
    IgnoreSpec,
    LintContext,
    LinterIssue,
    Severity,
    Stage,
    should_ignore,
)
from .base import AbstractLinter

__all__ = [
    "ExitCode",
    "IgnoreConfig",
    "IgnoreSpec",
    "LintContext",
    "LinterIssue",
    "Severity",
    "Stage",
    "should_ignore",
    "AbstractLinter",
]
