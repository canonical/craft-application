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
"""Abstract base for linters used by the linter service."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable

    from .types import LintContext, LinterIssue, Stage


class AbstractLinter(ABC):
    """Base class for all linters.

    Linters should set:
      - name: stable identifier (used in ignore config)
      - stage: Stage.PRE or Stage.POST
    """

    name: str
    stage: Stage

    @abstractmethod
    def run(self, ctx: LintContext) -> Iterable[LinterIssue]:
        """Execute the linter and yield issues."""
