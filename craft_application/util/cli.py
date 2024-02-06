# Copyright 2024 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Command-line utility functions."""
import sys

from craft_cli import emit

_BOOL_CHOICES = {True: "[Y/n]", False: "[y/N]", None: "[y/n]"}


def read_bool(prompt: str, default: bool | None = True) -> bool:
    """Get a yes/no value from the user as a boolean.

    If `default` is None, it's possible to receive a None back as well.
    """
    if not sys.stdin.isatty():
        return default

    choices = _BOOL_CHOICES[default]
    full_prompt = f"{prompt} {choices}: "

    with emit.pause():
        while True:
            user_choice = input(full_prompt).strip().lower()

            if not user_choice and default is not None:
                return default
            if user_choice.startswith("y"):
                return True
            if user_choice.startswith("n"):
                return False
