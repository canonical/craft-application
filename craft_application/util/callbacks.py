#  This file is part of craft-application.
#
#  Copyright 2023 Canonical Ltd.
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
"""Utilities related to callbacks."""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Literal, overload

if TYPE_CHECKING:  # pragma: no cover
    # Caution: Removing these from type checking will result in circular imports.
    from craft_application.commands.base import ParserCallback, RunCallback


@overload
def get_unique_callbacks(
    cls: type, callback_name: Literal["_parse_callback"]
) -> Iterable[ParserCallback]: ...  # pragma: no cover


@overload
def get_unique_callbacks(
    cls: type, callback_name: Literal["_prologue", "_epilogue"]
) -> Iterable[RunCallback]: ...  # pragma: no cover


def get_unique_callbacks(  # pyright: ignore[reportUnknownParameterType]
    cls: type, callback_name: str
) -> Iterable[Callable]:  # type: ignore[type-arg]
    """Get all unique callbacks in a class's inheritance tree.

    Guarantees order to be the reverse of the method resolution order (that is,
    starting with ``object`` and working its way down the resolution tree to the
    class itself). This means that the callbacks for child classes may depend on
    or modify the results of the callbacks for the parent class.

    :param cls:  The class to search for callbacks
    :param callback_name:  The name of the function
    :return: Ordered callbacks starting at the top of the class tree.
    """
    callbacks = []  # pyright: ignore[reportUnknownVariableType]
    for class_ in reversed(cls.mro()):
        callback = getattr(class_, callback_name, None)
        if callback is not None and callback not in callbacks:
            callbacks.append(callback)  # pyright: ignore[reportUnknownMemberType]
    return callbacks  # pyright: ignore[reportUnknownVariableType]
