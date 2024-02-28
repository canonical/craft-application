#  This file is part of craft-application.
#
#  Copyright 2024 Canonical Ltd.
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
"""String related functions."""


def strtobool(value: str) -> bool:
    """Try to convert a string to a boolean.

    If the value is not a string, a TypeError is raised.
    If the value is not a valid boolean value, a ValueError is raised.
    """
    if not isinstance(value, str):  # type: ignore[reportUnnecessaryIsInstance]
        raise TypeError(f"Invalid str value: {str(value)}")

    value = value.strip().lower()
    if value in {"true", "t", "yes", "y", "on", "1"}:
        return True
    if value in {"false", "f", "no", "n", "off", "0"}:
        return False
    raise ValueError(f"Invalid boolean value: {value}")
