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
"""Service class to communicate with the fetch-service."""

import craft_providers
from typing_extensions import override

from craft_application import services


class FetchService(services.AppService):
    """Service class that handles communication with the fetch-service.

    This Service is able to spawn a fetch-service instance and create sessions
    to be used in managed runs. The general usage flow is this:

    - Initialise a fetch-service via setup() (done automatically by the service
      factory);
    - For each managed execution:
      - Create a new session with create_session(), passing the new managed
        instance;
      - Teardown/close the session with teardown_session();
    - Stop the fetch-service via shutdown().
    """

    @override
    def setup(self) -> None:
        """Start the fetch-service process with proper arguments."""
        # Things to do here:
        # - Figure out available ports
        # - Spawn the service (from the snap?)

    def create_session(
        self,
        instance: craft_providers.Executor,  # noqa: ARG002 (unused-method-argument)
    ) -> dict[str, str]:
        """Create a new session.

        :return: The environment variables that must be used by any process
          that will use the new session.
        """
        # Things to do here (from the prototype):
        # To create the session:
        # - Create a session (POST), store session data
        # - Find the gateway for the network used by the instance (need API)
        # - Return http_proxy/https_proxy with session data
        #
        # To configure the instance:
        # - Install bundled certificate
        # - Configure snap proxy
        # - Clean APT's cache
        return {}

    def teardown_session(self) -> None:
        """Teardown and cleanup a previously-created session."""
        # Things to do here (from the prototype):
        # - Dump service status (where?)
        # - Revoke session token
        # - Dump session report
        # - Delete session
        # - Clean session resources?

    def shutdown(self) -> None:
        """Stop the fetch-service."""
