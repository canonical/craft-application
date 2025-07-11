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

import atexit
import json
import pathlib
import typing
from functools import partial

from craft_cli import emit
from typing_extensions import override

from craft_application import fetch, util
from craft_application.models.manifest import CraftManifest, ProjectManifest
from craft_application.services import base

if typing.TYPE_CHECKING:
    import subprocess

    import craft_providers

    from craft_application.application import AppMetadata
    from craft_application.services import service_factory


_PROJECT_MANIFEST_MANAGED_PATH = pathlib.Path(
    "/tmp/craft-project-manifest.yaml"  # noqa: S108 (possibly insecure)
)


class FetchService(base.AppService):
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
    _instance: craft_providers.Executor | None

    def __init__(
        self,
        app: AppMetadata,
        services: service_factory.ServiceFactory,
    ) -> None:
        """Create a new FetchService.

        :param session_policy: Whether the created fetch-service sessions should
          be "strict" or "permissive".
        """
        super().__init__(app, services)
        self._fetch_process = None
        self._session_data = None
        self._session_policy: str = "strict"  # Default to strict policy.
        self._instance = None

    @override
    def setup(self) -> None:
        """Start the fetch-service process with proper arguments."""
        super().setup()

        if not util.is_managed_mode():
            # Early fail if the fetch-service is not installed.
            fetch.verify_installed()

            # Emit a warning, but only on the host-side.
            logpath = fetch.get_log_filepath()
            emit.message(
                "Warning: the fetch-service integration is experimental. "
                f"Logging output to {str(logpath)!r}."
            )

            self._fetch_process = fetch.start_service()

            # When we exit the application, we'll shut down the fetch service.
            atexit.register(self.shutdown, force=True)

    def set_policy(self, policy: typing.Literal["strict", "permissive"]) -> None:
        """Set the policy for the fetch service."""
        self._session_policy = policy

    def create_session(self, instance: craft_providers.Executor) -> dict[str, str]:
        """Create a new session.

        :return: The environment variables that must be used by any process
          that will use the new session.
        """
        if self._session_data is not None:
            raise ValueError(
                "create_session() called but there's already a live fetch-service session."
            )
        strict_session = self._session_policy == "strict"
        self._session_data = fetch.create_session(strict=strict_session)
        self._instance = instance
        emit.progress("Configuring fetch-service integration")
        return fetch.configure_instance(instance, self._session_data)

    def teardown_session(self) -> dict[str, typing.Any]:
        """Teardown and cleanup a previously-created session."""
        if self._session_data is None or self._instance is None:
            raise ValueError(
                "teardown_session() called with no live fetch-service session."
            )
        report = fetch.teardown_session(self._session_data)

        instance = self._instance
        instance_path = _PROJECT_MANIFEST_MANAGED_PATH
        with instance.temporarily_pull_file(source=instance_path, missing_ok=True) as f:
            if f is not None:
                # Project manifest was generated; we can create the full manifest
                self._create_craft_manifest(f, report)
            else:
                emit.debug("Project manifest file missing in managed instance.")

        self._session_data = None
        self._instance = None

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
        build = self._services.get("build_plan").plan()[0]
        # mypy doesn't accept accept ignore[union-attr] for unknown reasons.
        if not self._services.ProviderClass.is_managed():  # type: ignore  # noqa: PGH003
            emit.debug("Unable to generate the project manifest on the host.")
            return

        emit.debug(f"Generating project manifest at {_PROJECT_MANIFEST_MANAGED_PATH}")
        project = self._services.get("project").get()
        project_manifest = ProjectManifest.from_packed_artifact(
            project, build, artifacts[0]
        )
        project_manifest.to_yaml_file(_PROJECT_MANIFEST_MANAGED_PATH)

    def _create_craft_manifest(
        self, project_manifest: pathlib.Path, session_report: dict[str, typing.Any]
    ) -> None:
        project = self._services.get("project").get()
        name = project.name
        version = project.version
        platform = self._services.get("build_plan").plan()[0].platform

        manifest_path = pathlib.Path(f"{name}_{version}_{platform}.json")
        emit.debug(f"Generating craft manifest at {manifest_path}")

        craft_manifest = CraftManifest.create_craft_manifest(
            project_manifest, session_report
        )
        data = craft_manifest.marshal()

        with manifest_path.open("w") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        deps = craft_manifest.dependencies
        rejections = [dep for dep in deps if dep.rejected]

        if rejections:
            display = partial(emit.progress, permanent=True)
            items: list[dict[str, typing.Any]] = []
            for rejection in rejections:
                url = rejection.url[0] if len(rejection.url) == 1 else rejection.url
                items.append({"url": url, "reasons": rejection.rejection_reasons})
            text = util.dump_yaml(items)

            display(
                "The following artifacts were marked as rejected by the fetch-service:"
            )
            for line in text.splitlines():
                display(line)
            display("This build will fail on 'strict' fetch-service sessions.")
