# This file is part of craft_application.
#
# Copyright 2024 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Utility functions and helpers prompting."""

import getpass
import sys
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext

from craft_application import errors

from .platforms import is_managed_mode


def prompt(
    prompt_text: str,
    *,
    hide: bool = False,
    prompting_context: type[AbstractContextManager[None]] = nullcontext,
) -> str:
    """Prompt and return the entered string.

    :param prompt_text: string used for the prompt.
    :param hide: hide user input if True.
    """
    method: Callable[[str], str] = getpass.getpass if hide else input  # type: ignore[assignment]

    if is_managed_mode():
        raise RuntimeError("prompting not yet supported in managed-mode")

    if not sys.stdin.isatty():
        raise errors.CraftError("prompting not possible with no tty")

    # replace with `craft_cli.emitter.prompt` once delivered
    with prompting_context():
        return method(prompt_text)
