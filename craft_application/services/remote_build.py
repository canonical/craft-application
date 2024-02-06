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
"""Service class for lifecycle commands."""
from __future__ import annotations

import datetime
import os
import time
import urllib.parse
from collections.abc import Collection, Iterable, Mapping
from typing import TYPE_CHECKING, cast
from urllib import parse

import craft_cli
import platformdirs

from craft_application import errors, launchpad
from craft_application.remote import GitRepo, WorkTree, utils
from craft_application.services import base, request

if TYPE_CHECKING:  # pragma: no cover
    import pathlib

    from craft_application import AppMetadata, ServiceFactory

DEFAULT_POLL_INTERVAL = 30


def _get_launchpad_instance(default: str = "production") -> str:
    return os.getenv("CRAFT_LAUNCHPAD_INSTANCE", default)


class RemoteBuildService(base.AppService):
    """Abstract service for performing remote builds."""

    RecipeClass: type[launchpad.models.Recipe]
    lp: launchpad.Launchpad
    lp_user: str
    _deadline: int | None = None
    """The deadline for the builds. Raises a TimeoutError if we surpass this."""

    def __init__(self, app: AppMetadata, services: ServiceFactory):
        super().__init__(app=app, services=services)
        self._name = ""
        self._repository: launchpad.models.GitRepository | None = None
        self._recipe: launchpad.models.Recipe | None = None
        self._builds: list[launchpad.models.Build] | None = None
        self.request = cast(request.RequestService, self._services.request)

    def setup(self) -> None:
        """Set up the remote builder"""
        self.lp = self._get_lp_client()
        self.lp_user = self.lp.lp.me.name

    def _get_lp_client(self) -> launchpad.Launchpad:
        """Get the launchpad client for the remote builder."""
        with craft_cli.emit.pause():
            return launchpad.Launchpad.login(
                f"{self._app.name}/{self._app.version}",
                service_root=_get_launchpad_instance(),
                credentials_file=platformdirs.user_data_path(self._app.name)
                / "launchpad-credentials",
            )

    def _new_repository(
        self, project_dir: pathlib.Path
    ) -> tuple[WorkTree, launchpad.models.GitRepository]:
        """Create a repository on the local machine and on Launchpad."""
        work_tree = WorkTree(self._app.name, self._name, project_dir)
        work_tree.init_repo()
        lp_repository = launchpad.models.GitRepository.new(self.lp, self._name)

        token = lp_repository.get_access_token(
            f"{self._app.name} {self._app.version} remote build",
            expiry=datetime.datetime.now() + datetime.timedelta(seconds=60)
        )
        repo_url = parse.urlparse(lp_repository.git_https_url)
        push_url = repo_url._replace(
            netloc=f"{self.lp.lp.me.name}:{token}@{repo_url.netloc}"
        )

        local_repository = GitRepo(work_tree.repo_dir)
        local_repository.push_url(push_url.geturl(), "main")

        return work_tree, lp_repository

    def _get_repository(self) -> None:
        """Get an existing repository on Launchpad."""
        self._repository = launchpad.models.GitRepository.get(
            self.lp, name=self._name, owner=self.lp_user
        )

    def _new_recipe(
        self,
        name: str,
        repository: launchpad.models.GitRepository,
        architectures: Collection[str] | None = None,
    ) -> launchpad.models.Recipe:
        """Create a new recipe."""
        return self.RecipeClass.new(
            self.lp,
            name,
            self.lp_user,
            git_ref=repository.git_https_url,
            architectures=architectures,
        )

    def _get_recipe(self) -> launchpad.models.Recipe:
        """Get a build for this application by its build ID.

        If an application's recipe class needs more than just the name and owner,
        this method and new_recipe should be overridden.
        """
        return self.RecipeClass.get(self.lp, self._name, self.lp_user)

    def _new_builds(
        self, recipe: launchpad.models.Recipe
    ) -> Collection[launchpad.models.Build]:
        """Create a build from a Launchpad repository."""
        return recipe.build(deadline=self._deadline)

    def _get_builds(self) -> list[launchpad.models.Build]:
        """Get the builds for a recipe by its name."""
        return self._recipe._get_builds()

    def _get_build_states(self) -> Mapping[str, launchpad.models.BuildState]:
        self._refresh_builds()
        return {build.arch_tag: build.get_status for build in self._builds}

    def _refresh_builds(self) -> None:
        """Refresh the data for builds from Launchpad."""
        for build in self._builds:
            build.lp_refresh()

    def _get_artifact_urls(self) -> Collection[str]:
        """Get the locations of all build artifacts."""
        return [*(build.get_entity().getFileUrls() for build in self._builds)]

    def set_timeout(self, seconds_in_future: int) -> None:
        """Set the deadline to a certain number of seconds in the future"""
        self._deadline = time.monotonic_ns() + (seconds_in_future * 10**9)

    def start_builds(
        self, project_dir: pathlib.Path, architectures: Collection[str] | None = None
    ) -> Collection[launchpad.models.Build]:
        """Start one or more builds for the project.

        This method requires a project to be loaded.
        """
        if self._builds is not None:
            raise ValueError("Cannot start builds if already running builds")

        self._name = utils.get_build_id(
            self._app.name, self._services.project.name, project_dir
        )

        work_tree, self._repository = self._new_repository(project_dir)
        self._recipe = self._new_recipe(self._name, self._repository, architectures)
        self._builds = list(self._new_builds(self._recipe))
        return self._builds

    def resume_builds(self, name: str) -> Collection[launchpad.models.Build]:
        """Resume monitoring for one or more remote builds."""
        self._name = name
        self._repository = self._get_repository()
        self._recipe = self._get_recipe()
        self._builds = self._get_builds()
        return self._builds

    def monitor_builds(
        self, poll_interval: float = DEFAULT_POLL_INTERVAL, deadline: int | None = None
    ) -> Iterable[Mapping[str, launchpad.models.BuildState]]:
        """Monitor builds.

        Exits once all builds have stopped. A return does not mean success.
        """
        while deadline is None or time.monotonic_ns() < deadline:
            states = self._get_build_states()
            yield states
            if all(status.is_stopping_or_stopped for status in states.values()):
                return
            time.sleep(poll_interval)

        yield self._get_build_states()

        raise TimeoutError("Monitoring builds timed out.")

    def fetch_logs(self, output_dir: pathlib.Path) -> Mapping[str, pathlib.Path | None]:
        """Fetch the logs for each build to the given directory.

        :param output_dir: The directory into which to place the logs.
        :returns: A mapping of the architecture to its build log.
        """
        logs: dict[str, pathlib.Path | None] = {}
        log_downloads: dict[str, pathlib.Path] = {}
        fetch_time = datetime.datetime.now().isoformat()
        for build in self._builds:
            url = build.build_log_url
            if not url:
                logs[build.arch_tag] = None
                continue
            filename = (
                f"{self._services.project.name}_{build.arch_tag}-{fetch_time}.txt"
            )
            logs[build.arch_tag] = output_dir / filename
        self.request.download_files_with_progress(log_downloads)
        return logs

    def fetch_artifacts(self, output_dir: pathlib.Path) -> Collection[pathlib.Path]:
        """Fetch the artifacts for each build."""
        artifact_downloads: dict[str, pathlib.Path] = {}
        for url in self._get_artifact_urls():
            filename = pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name
            artifact_downloads[url] = output_dir / filename
        return self.request.download_files_with_progress(artifact_downloads).values()

    def cancel_builds(self) -> None:
        """Cancel all running builds for a recipe."""
        cancel_failed = []
        for build in self._builds:
            try:
                build.cancel()
            except launchpad.errors.BuildError as exc:
                cancel_failed.append(exc.args[0])
        if cancel_failed:
            raise errors.CancelFailedError(cancel_failed)

    def cleanup(self) -> None:
        """Clean up the recipe and repository."""
        if self._recipe is not None:
            self._recipe.delete()
        if self._repository is not None:
            self._repository.delete()
