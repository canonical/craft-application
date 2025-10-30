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

import inspect as _inspect
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from ._types import Stage as _Stage

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterable

    from ._types import LintContext, LinterIssue, Stage


class AbstractLinter(ABC):
    """Base class for all linters.

    Linters should set:
      - name: stable identifier (used in ignore config)
      - stage: Stage.PRE or Stage.POST
    """

    name: str
    stage: Stage

    def __init_subclass__(cls) -> None:
        """Validate subclass has required attributes."""
        super().__init_subclass__()

        if _inspect.isabstract(cls):
            return

        if not isinstance(getattr(cls, "name", None), str) or not cls.name:
            raise TypeError("Linter subclass must define a non-empty 'name' string.")
        if not isinstance(getattr(cls, "stage", None), _Stage):
            raise TypeError("Linter subclass must define 'stage' as a Stage enum.")

    @abstractmethod
    def run(self, ctx: LintContext) -> Iterable[LinterIssue]:
        """Execute the linter and yield issues."""
