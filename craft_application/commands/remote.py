# Copyright 2024 Canonical Ltd.
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
"""Build a project remotely on Launchpad."""

import argparse
import os
import pathlib
import time
from collections.abc import Collection
from typing import Any, cast

from craft_cli import emit
from overrides import override  # pyright: ignore[reportUnknownVariableType]

from craft_application import models
from craft_application.commands import ExtensibleCommand
from craft_application.launchpad.models import Build, BuildState
from craft_application.remote.utils import get_build_id

OVERVIEW = """
Command remote-build sends the current project to be built
remotely. After the build is complete, packages for each
architecture are retrieved and will be available in the
local filesystem.

Interrupted remote builds can be resumed using the --recover
option.

To set a timeout on the remote-build command, use the option
``--launchpad-timeout=<seconds>``. The timeout is local, so
the build on launchpad will continue even if the local instance
is interrupted or times out.
"""

_CONFIRMATION_PROMPT = (
    "All data sent to remote builders will be publicly available. "
    "Are you sure you want to continue?"
)


class RemoteBuild(ExtensibleCommand):
    """Build a project on Launchpad."""

    name = "remote-build"
    help_msg = "Build a project remotely on Launchpad."
    overview = OVERVIEW
    always_load_project = True

    @override
    def _fill_parser(self, parser: argparse.ArgumentParser) -> None:
        parser.add_argument(
            "--recover", action="store_true", help="recover an interrupted build"
        )
        parser.add_argument(
            "--launchpad-accept-public-upload",
            action="store_true",
            help="acknowledge that uploaded code will be publicly available.",
        )
        parser.add_argument(
            "--launchpad-timeout",
            type=int,
            default=0,
            metavar="<seconds>",
            help="Time in seconds to wait for launchpad to build.",
        )

    def _run(
        self,
        parsed_args: argparse.Namespace,
        **_kwargs: Any,
    ) -> int | None:
        """Run the remote-build command.

        :param parsed_args: parsed argument namespace from craft_cli.

        :raises AcceptPublicUploadError: If the user does not agree to upload data.
        """
        if os.getenv("SUDO_USER") and os.geteuid() == 0:
            emit.progress(
                "Running with 'sudo' may cause permission errors and is discouraged.",
                permanent=True,
            )
            # Give the user a bit of time to process this before proceeding.
            time.sleep(1)

        emit.progress(
            "remote-build is experimental and is subject to change. Use with caution.",
            permanent=True,
        )

        if not parsed_args.launchpad_accept_public_upload and not emit.confirm(
            _CONFIRMATION_PROMPT, default=False
        ):
            emit.message("Cannot proceed without accepting a public upload.")
            return 77  # permission denied from sysexits.h

        builder = self._services.remote_build
        project = cast(models.Project, self._services.project)
        config = cast(dict[str, Any], self.config)
        project_dir = (
            pathlib.Path(config.get("global_args", {}).get("project_dir") or ".")
            .expanduser()
            .resolve()
        )
        emit.trace(f"Project directory: {project_dir}")

        if parsed_args.launchpad_timeout:
            emit.debug(f"Setting timeout to {parsed_args.launchpad_timeout} seconds")
            builder.set_timeout(parsed_args.launchpad_timeout)

        build_id = get_build_id(self._app.name, project.name, project_dir)
        if parsed_args.recover:
            emit.progress(f"Recovering build {build_id}")
            builds = builder.resume_builds(build_id)
        else:
            emit.progress(
                "Starting new build. It may take a while to upload large projects."
            )
            builds = builder.start_builds(project_dir)

        try:
            returncode = self._monitor_and_complete(builds=builds)
        except KeyboardInterrupt:
            if emit.confirm("Cancel builds?", default=True):
                emit.progress("Cancelling builds.")
                builder.cancel_builds()
                emit.progress("Cleaning up")
                builder.cleanup()
            returncode = 0
        except TimeoutError:
            resume_command = f"{self._app.name} remote-build --recover"
            emit.message(
                f"Timed out waiting for build.\nTo resume, run {resume_command!r}"
            )
            return 75  # os.EX_TEMPFAIL
        else:
            emit.progress("Cleaning up")
            builder.cleanup()
        return returncode

    def _monitor_and_complete(self, *, builds: Collection[Build]) -> int:
        """Monitor the builds and complete them when done.

        :param builds: A collection of Builds to monitor.
        :returns: The expected exit code of the application.
        :raises: TimeoutError if a build timeout was reached.
        """
        builder = self._services.remote_build
        emit.progress("Monitoring build")
        for states in builder.monitor_builds():
            building: set[str] = set()
            succeeded: set[str] = set()
            uploading: set[str] = set()
            not_building: set[str] = set()
            for arch, build_state in states.items():
                if build_state.is_running:
                    building.add(arch)
                elif build_state == BuildState.SUCCESS:
                    succeeded.add(arch)
                elif build_state == BuildState.UPLOADING:
                    uploading.add(arch)
                else:
                    not_building.add(arch)
            progress_parts: list[str] = []
            if not_building:
                progress_parts.append("Stopped: " + ", ".join(sorted(not_building)))
            if building:
                progress_parts.append("Building: " + ", ".join(sorted(building)))
            if uploading:
                progress_parts.append("Uploading: " + ", ".join(sorted(uploading)))
            if succeeded:
                progress_parts.append("Succeeded: " + ", ".join(sorted(succeeded)))
            emit.progress("; ".join(progress_parts))

        emit.progress("Fetching build artifacts...")
        artifacts = builder.fetch_artifacts(pathlib.Path.cwd())

        emit.progress(f"Fetching {len(builds)} build logs...")
        logs = builder.fetch_logs(pathlib.Path.cwd())

        log_names = sorted(path.name for path in logs.values() if path)
        artifact_names = sorted(path.name for path in artifacts)

        emit.message(
            "Build completed.\n"
            f"Log files: {', '.join(log_names)}\n"
            f"Artifacts: {', '.join(artifact_names)}"
        )
        return 0
