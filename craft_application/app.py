# This file is part of craft_application.
#
# Copyright 2023 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Main application classes for a craft-application."""
from __future__ import annotations

from dataclasses import dataclass, field
from importlib import metadata
from typing import final

from craft_application import models


@final
@dataclass(frozen=True)
class AppMetadata:
    """Metadata about a *craft application."""

    name: str
    summary: str | None = None
    version: str = field(init=False)
    source_ignore_patterns: list[str] = field(default_factory=lambda: [])

    ProjectClass: type[models.Project] = models.Project

    def __post_init__(self) -> None:
        setter = super().__setattr__
        setter("version", metadata.version(self.name))
        if self.summary is None:
            md = metadata.metadata(self.name)
            setter("summary", md["summary"])
