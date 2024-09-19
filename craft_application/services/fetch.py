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
from __future__ import annotations

import json
import pathlib
import subprocess
import typing

import craft_providers
from craft_cli import emit
from typing_extensions import override

from craft_application import fetch, models, services
from craft_application.models.manifest import ProjectManifest

if typing.TYPE_CHECKING:
    from craft_application.application import AppMetadata


_PROJECT_MANIFEST_MANAGED_PATH = pathlib.Path(
    "/tmp/craft-project-manifest.yaml"  # noqa: S108 (possibly insecure)
)


class FetchService(services.ProjectService):
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

    _fetch_process: subprocess.Popen[str] | None
    _session_data: fetch.SessionData | None

    def __init__(
        self,
        app: AppMetadata,
        services: services.ServiceFactory,
        *,
        project: models.Project,
        build_plan: list[models.BuildInfo],
    ) -> None:
        super().__init__(app, services, project=project)
        self._fetch_process = None
        self._session_data = None
        self._build_plan = build_plan

    @override
    def setup(self) -> None:
        """Start the fetch-service process with proper arguments."""
        super().setup()
        self._fetch_process = fetch.start_service()

    def create_session(self, instance: craft_providers.Executor) -> dict[str, str]:
        """Create a new session.

        :return: The environment variables that must be used by any process
          that will use the new session.
        """
        if self._session_data is not None:
            raise ValueError(
                "create_session() called but there's already a live fetch-service session."
            )

        self._session_data = fetch.create_session()
        return fetch.configure_instance(instance, self._session_data)

    def teardown_session(self) -> dict[str, typing.Any]:
        """Teardown and cleanup a previously-created session."""
        if self._session_data is None:
            raise ValueError(
                "teardown_session() called with no live fetch-service session."
            )
        report = fetch.teardown_session(self._session_data)

        # TODO for now we just dump the session report locally
        # (will use it in the future to create a manifest)
        report_path = pathlib.Path("session-report.json")
        with report_path.open("w") as f:
            json.dump(report, f, ensure_ascii=False, indent=4)
        emit.debug(f"Session report dumped to {report_path}")

        self._session_data = None
        return report

    def shutdown(self, *, force: bool = False) -> None:
        """Stop the fetch-service.

        The default behavior is a no-op; the Application never shuts down the
        fetch-service so that it stays up and ready to serve other craft
        applications.

        :param force: Whether the fetch-service should be, in fact, stopped.
        """
        if force and self._fetch_process:
            fetch.stop_service(self._fetch_process)

    def create_project_manifest(self, artifacts: list[pathlib.Path]) -> None:
        """Create the project manifest for the artifact in ``artifacts``.

        Only supports a single generated artifact, and only in managed runs.
        """
        if not self._services.ProviderClass.is_managed():
            emit.debug("Unable to generate the project manifest on the host.")
            return

        emit.debug(f"Generating project manifest at {_PROJECT_MANIFEST_MANAGED_PATH}")
        project_manifest = ProjectManifest.from_packed_artifact(
            self._project, self._build_plan[0], artifacts[0]
        )
        project_manifest.to_yaml_file(_PROJECT_MANIFEST_MANAGED_PATH)
