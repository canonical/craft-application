# This file is part of craft_application.
#
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
"""Init service override for Testcraft."""

from craft_application.services import InitService as BaseInitService
from typing_extensions import override


class InitService(BaseInitService):
    """Init service override for Testcraft."""

    @override
    def _vcs_ignore_lines(self) -> list[str]:
        return [*super()._vcs_ignore_lines, "/*.test"]
