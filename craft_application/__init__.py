# This file is part of craft-application.
#
# Copyright 2023 Canonical Ltd.
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
"""Framework for *craft applications."""

from craft_application.application import Application, AppFeatures, AppMetadata
from craft_application import models
from craft_application.services import (
    AppService,
    ProjectService,
    LifecycleService,
    PackageService,
    ProviderService,
    ServiceFactory,
)
from craft_application._config import ConfigModel

try:
    from ._version import __version__
except ImportError:  # pragma: no cover
    from importlib.metadata import version, PackageNotFoundError

    try:
        __version__ = version("craft-application")
    except PackageNotFoundError:
        __version__ = "dev"

__all__ = [
    "__version__",
    "Application",
    "AppFeatures",
    "AppMetadata",
    "AppService",
    "ConfigModel",
    "models",
    "ProjectService",
    "LifecycleService",
    "PackageService",
    "ProviderService",
    "ServiceFactory",
]
