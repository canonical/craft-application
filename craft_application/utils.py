#  This file is part of craft-application.
#
#  2023 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
import os
import sys
from typing import Optional

from craft_application.errors import CraftEnvironmentError

TRUTHY_STRINGS = frozenset({'y', 'yes', 'true', 'on', '1'})
FALSEY_STRINGS = frozenset({'', 'n', 'no', 'false', 'off', '0'})


def get_env_bool(var: str) -> Optional[bool]:
    """Get an environment variable as a boolean.

    :param var: The name of the variable to get
    :returns True if the value appears true, False if it appears false, None if unset.
    :raises: CraftEnvironmentError if the value is not parseable.
    """
    if var not in os.environ:
        return None
    value = os.environ[var]
    if value not in TRUTHY_STRINGS | FALSEY_STRINGS:
        raise CraftEnvironmentError(var, value)
    return value in TRUTHY_STRINGS


def confirm_with_user(prompt: str, default: bool = False) -> bool:
    """Query user for yes/no answer.

    If stdin is not a tty, the default value is returned.

    If user returns an empty answer, the default value is returned.
    returns default value.

    :returns: True if answer starts with [yY], False if answer starts with [nN],
        otherwise the default.
    """
    if not sys.stdin.isatty():
        return default

    choices = " [Y/n]: " if default else " [y/N]: "

    reply = input(prompt + choices).lower().strip()
    return reply[0] == "y" if reply else default
