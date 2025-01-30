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
"""Command classes for a craft application."""

from .base import AppCommand, ExtensibleCommand
from . import lifecycle
from .init import InitCommand
from .lifecycle import get_lifecycle_command_group, LifecycleCommand
from .other import get_other_command_group
from .remote import RemoteBuild  # Not part of the default commands.

__all__ = [
    "AppCommand",
    "ExtensibleCommand",
    "InitCommand",
    "RemoteBuild",
    "lifecycle",
    "LifecycleCommand",
    "get_lifecycle_command_group",
    "get_other_command_group",
]
