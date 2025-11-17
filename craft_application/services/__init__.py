#  This file is part of craft-application.
#
#  Copyright 2023-2025 Canonical Ltd.
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
"""Service classes for the business logic of various categories of command."""

from craft_application.services.base import AppService
from craft_application.services.config import ConfigService
from craft_application.services.fetch import FetchService
from craft_application.services.lifecycle import LifecycleService
from craft_application.services.init import InitService
from craft_application.services.testing import TestingService
from craft_application.services.package import PackageService
from craft_application.services.project import ProjectService
from craft_application.services.provider import ProviderService
from craft_application.services.proxy import ProxyService
from craft_application.services.remotebuild import RemoteBuildService
from craft_application.services.request import RequestService
from craft_application.services.state import StateService

# ServiceFactory must be imported after the actual services
from craft_application.services.service_factory import ServiceFactory

__all__ = [
    "AppService",
    "ConfigService",
    "FetchService",
    "InitService",
    "LifecycleService",
    "PackageService",
    "ProjectService",
    "ProviderService",
    "ProxyService",
    "RemoteBuildService",
    "RequestService",
    "ServiceFactory",
    "StateService",
    "TestingService",
]
