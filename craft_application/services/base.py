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
"""Abstract base service class."""
import abc

from craft_application import AppMetadata, models


# ignoring the fact that this abstract class has no abstract methods.
class BaseService(metaclass=abc.ABCMeta):  # noqa: B024
    """A service containing the actual business logic of one or more commands."""

    def __init__(self, app: AppMetadata, project: models.Project) -> None:
        self._app = app
        self._project = project
