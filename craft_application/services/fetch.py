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
import os
import pathlib
import typing
from functools import partial

from craft_cli import emit
from typing_extensions import override

from craft_application import errors, fetch, util
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

# Whether we should use an existing fetch-service session, managed by someone else
EXTERNAL_FETCH_SERVICE_ENV_VAR = "CRAFT_USE_EXTERNAL_FETCH_SERVICE"
# The location of the certificate of the externally-managed fetch-service
PROXY_CERT_ENV_VAR = "CRAFT_PROXY_CERT"


def _use_external_session() -> bool:
    return os.getenv(EXTERNAL_FETCH_SERVICE_ENV_VAR) == "1"


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
    _proxy_cert: pathlib.Path | None

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
        self._proxy_cert = None
        self._external_session = False

    @override
    def setup(self) -> None:
        """Start the fetch-service process with proper arguments."""
        super().setup()

        self._external_session = _use_external_session()

        if self._external_session:
            cert_str = os.getenv(PROXY_CERT_ENV_VAR)
            if cert_str is None:
                brief = f"Environment variable {PROXY_CERT_ENV_VAR!r} is not set"
                details = (
                    "An external fetch-service session cannot be used without"
                    " the certificate file."
                )
                raise errors.CraftError(brief, details=details)

            cert_path = pathlib.Path(cert_str)
            if not cert_path.is_file():
                brief = f"{cert_path} is not a valid certificate file."
                raise errors.CraftError(brief)

            self._proxy_cert = cert_path
        elif not util.is_managed_mode():
            # Early fail if the fetch-service is not installed.
            fetch.verify_installed()

            # Emit a warning, but only on the host-side.
            logpath = fetch.get_log_filepath()
            emit.message(
                "Warning: the fetch-service integration is experimental. "
                f"Logging output to {str(logpath)!r}."
            )

            self._fetch_process, self._proxy_cert = fetch.start_service()

            # When we exit the application, we'll shut down the fetch service.
            atexit.register(self.shutdown, force=True)

    def set_policy(self, policy: typing.Literal["strict", "permissive"]) -> None:
        """Set the policy for the fetch service."""
        self._session_policy = policy

    @staticmethod
    def is_active(*, enable_command_line: bool) -> bool:
        """Whether the FetchService will be used in managed runs.

        This can happen if:

        - ``enable_command_line`` is True, in which case the service will create and
            teardown fetch-service sessions;
        -  CRAFT_USE_EXTERNAL_FETCH_SERVICE is True, in which case the service will use
            a *pre-existing* fetch-service session.
        """
        use_external_session = _use_external_session()
        if use_external_session and enable_command_line:
            brief = (
                "Conflicting request for both external and managed fetch-service use."
            )
            raise errors.CraftError(brief)
        return enable_command_line or _use_external_session()

    def configure_instance(self, instance: craft_providers.Executor) -> dict[str, str]:
        """Configure an instance for use with the fetch-service.

        This method is a "superset" of ``create_session()`` and handles both cases:

        - Cases where "--enable-fetch-service" is passed on the command line and the
          application will handle the fetch-service and its session;
        - Cases where "CRAFT_USE_EXTERNAL_FETCH_SERVICE" is set and the application
          has to configure the instance to use the existing, externally-created session.

        :return: The environment variables that must be used by any process
          that will use the new session.
        """
        if self._external_session:
            proxy_url = os.getenv("http_proxy")
            if proxy_url is None:
                raise errors.CraftError(
                    "External fetch-service session requested but 'http_proxy' is not set."
                )
            if self._proxy_cert is None:
                raise ValueError("configure_instance() was called before setup().")
            self._services.get("proxy").configure(self._proxy_cert, proxy_url)
            return fetch.NetInfo.env()

        return self.create_session(instance)

    def create_session(self, instance: craft_providers.Executor) -> dict[str, str]:
        """Create a new session.

        :return: The environment variables that must be used by any process
          that will use the new session.
        """
        if self._session_data is not None:
            raise ValueError(
                "create_session() called but there's already a live fetch-service session."
            )
        if self._proxy_cert is None:
            raise ValueError(
                "create_session() was called before setting up the fetch service."
            )

        strict_session = self._session_policy == "strict"
        self._session_data = fetch.create_session(strict=strict_session)
        self._instance = instance
        net_info = fetch.NetInfo(instance, self._session_data)
        self._services.get("proxy").configure(self._proxy_cert, net_info.http_proxy)
        return net_info.env()

    def teardown_instance(self) -> dict[str, typing.Any]:
        """Teardown whatever configuration was done on a managed instance.

        This method is a superset of ``teardown_session()`` and should be used instead.
        """
        if self._external_session:
            return {}  # Nothing to do

        return self.teardown_session()

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
        # This can be called with a multi-item build plan, so just get the first.
        build = self._services.get("build_plan").plan()[0]
        # mypy doesn't accept accept ignore[union-attr] for unknown reasons.
        if not self._services.ProviderClass.is_managed():  # type: ignore  # noqa: PGH003
            emit.debug("Unable to generate the project manifest on the host.")
            return

        emit.debug(f"Generating project manifest at {_PROJECT_MANIFEST_MANAGED_PATH}")
        project_manifest = ProjectManifest.from_packed_artifact(
            self._project, build, artifacts[0]
        )
        project_manifest.to_yaml_file(_PROJECT_MANIFEST_MANAGED_PATH)

    def _create_craft_manifest(
        self, project_manifest: pathlib.Path, session_report: dict[str, typing.Any]
    ) -> None:
        name = self._project.name
        version = self._project.version
        # This can be called with a multi-item build plan, so just get the first.
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
