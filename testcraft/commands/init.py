# Copyright 2026 Canonical Ltd.
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
"""Command to initialize a project."""

from __future__ import annotations

from craft_application.commands import InitCommand as BaseInitCommand
from typing_extensions import override


class InitCommand(BaseInitCommand):
    """Init command override for Testcraft."""

    @override
    @property
    def vcs_ignore_globs(self) -> list[str]:
        return [*super().vcs_ignore_globs, "/*.test"]
