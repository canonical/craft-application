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
"""Service class for remote build commands."""
from __future__ import annotations

import contextlib
import datetime
import itertools
import os
import pathlib
import time
import urllib.parse
from collections.abc import Collection, Iterable, Mapping
from typing import TYPE_CHECKING, Any, cast
from urllib import parse

import craft_cli
import launchpadlib.errors  # type: ignore[import-untyped]
import platformdirs

from craft_application import errors, launchpad, models
from craft_application.git import GitError, GitRepo
from craft_application.remote import (
    RemoteBuildGitError,
    WorkTree,
    check_git_repo_for_remote_build,
    utils,
)
from craft_application.services import base

if TYPE_CHECKING:  # pragma: no cover
    from craft_application import AppMetadata, ServiceFactory

DEFAULT_POLL_INTERVAL = 30


class RemoteBuildService(base.AppService):
    """Abstract service for performing remote builds."""

    RecipeClass: type[launchpad.models.Recipe]
    lp: launchpad.Launchpad
    _deadline: int | None = None
    """The deadline for the builds. Raises a TimeoutError if we surpass this."""

    def __init__(self, app: AppMetadata, services: ServiceFactory) -> None:
        super().__init__(app=app, services=services)
        self._name = ""
        self.request = self._services.request
        self._is_setup = False
        # Assigning these as None so they exist. They won't be accessed until they're
        # assigned the correct types though.
        self._lp_project: launchpad.models.Project = None  # type: ignore[assignment]
        self._repository: launchpad.models.GitRepository = None  # type: ignore[assignment]
        self._recipe: launchpad.models.recipe.BaseRecipe = None  # type: ignore[assignment]
        self._builds: Collection[launchpad.models.Build] = []
        self._project_name: str | None = None

    def setup(self) -> None:
        """Set up the remote builder."""
        self.lp = self._get_lp_client()

    @property
    def credentials_filepath(self) -> pathlib.Path:
        """The filepath to the Launchpad credentials."""
        return platformdirs.user_data_path(self._app.name) / "launchpad-credentials"

    # region Public API
    # Commands will call a subset of these methods, generally in order.
    def set_project(self, name: str) -> None:
        """Set the name of the project to use."""
        if self._is_setup:
            raise RuntimeError(
                "Project name may only be set before starting or resuming builds."
            )
        try:
            self._lp_project = self.lp.get_project(name)
        except launchpad.errors.NotFoundError:
            raise errors.CraftError(
                message=f"Could not find project on Launchpad: {name}",
                resolution="Ensure the project exists and that you have access to it.",
                retcode=os.EX_NOPERM,
                reportable=False,
                logpath_report=False,
            )
        self._project_name = name

    def is_project_private(self) -> bool:
        """Check whether the named project is private."""
        if not self._lp_project:
            raise RuntimeError(
                "Cannot check if the project is private before setting its name."
            )
        return self._lp_project.information_type not in (
            launchpad.models.InformationType.PUBLIC,
            launchpad.models.InformationType.PUBLIC_SECURITY,
        )

    def set_timeout(self, seconds_in_future: int) -> None:
        """Set the deadline to a certain number of seconds in the future."""
        self._deadline = time.monotonic_ns() + (seconds_in_future * 10**9)

    def start_builds(
        self, project_dir: pathlib.Path, architectures: Collection[str] | None = None
    ) -> Collection[launchpad.models.Build]:
        """Start one or more builds for the project.

        This method requires a project to be loaded.
        """
        if self._builds:
            raise ValueError("Cannot start builds if already running builds")

        project = cast(models.Project, self._services.project)

        check_git_repo_for_remote_build(project_dir)

        self._name = utils.get_build_id(self._app.name, project.name, project_dir)
        self._lp_project = self._ensure_project()
        _, self._repository = self._ensure_repository(project_dir)
        self._recipe = self._ensure_recipe(
            self._name, self._repository, architectures=architectures
        )
        self._check_timeout()
        self._builds = list(self._new_builds(self._recipe))
        self._is_setup = True
        return self._builds

    def resume_builds(self, name: str) -> Collection[launchpad.models.Build]:
        """Resume monitoring for one or more remote builds."""
        self._name = name
        self._lp_project = self._ensure_project()
        self._repository = self._get_repository()
        self._recipe = self._get_recipe()
        self._builds = self._get_builds()
        self._is_setup = True
        return self._builds

    def monitor_builds(
        self, poll_interval: float = DEFAULT_POLL_INTERVAL
    ) -> Iterable[Mapping[str, launchpad.models.BuildState]]:
        """Monitor builds.

        Exits once all builds have stopped. A return does not mean success.
        """
        if not self._is_setup:
            raise RuntimeError(
                "RemoteBuildService must be set up using start_builds or resume_builds before monitoring builds."
            )
        while self._deadline is None or time.monotonic_ns() < self._deadline:
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
        if not self._is_setup:
            raise RuntimeError(
                "RemoteBuildService must be set up using start_builds or resume_builds before fetching logs."
            )
        logs: dict[str, pathlib.Path | None] = {}
        log_downloads: dict[str, pathlib.Path] = {}
        fetch_time = datetime.datetime.now().isoformat(timespec="seconds")
        for build in self._builds:
            url = build.build_log_url
            if not url:
                logs[build.arch_tag] = None
                continue
            filename = f"{self._name}_{build.arch_tag}_{fetch_time}.txt"
            logs[build.arch_tag] = output_dir / filename
            log_downloads[url] = output_dir / filename
        self.request.download_files_with_progress(log_downloads)
        return logs

    def fetch_artifacts(self, output_dir: pathlib.Path) -> Collection[pathlib.Path]:
        """Fetch the artifacts for each build."""
        if not self._is_setup:
            raise RuntimeError(
                "RemoteBuildService must be set up using start_builds or resume_builds before fetching artifacts."
            )
        artifact_downloads: dict[str, pathlib.Path] = {}
        for url in self._get_artifact_urls():
            filename = pathlib.PurePosixPath(urllib.parse.urlparse(url).path).name
            artifact_downloads[url] = output_dir / filename
        return self.request.download_files_with_progress(artifact_downloads).values()

    def cancel_builds(self) -> None:
        """Cancel all running builds for a recipe."""
        if not self._is_setup:
            raise RuntimeError(
                "RemoteBuildService must be set up using start_builds or resume_builds before cancelling builds."
            )
        cancel_failed = []
        for build in self._builds:
            try:
                build.cancel()
            except launchpad.errors.BuildError as exc:
                cancel_failed.append(  # pyright: ignore[reportUnknownMemberType]
                    exc.args[0]
                )
        if cancel_failed:
            raise errors.CancelFailedError(
                cancel_failed  # pyright: ignore[reportUnknownArgumentType]
            )

    def cleanup(self) -> None:
        """Clean up the recipe and repository."""
        # Pyright complains about these comparisons because we're doing hacky things to
        # the type system.
        if self._recipe is not None:  # pyright: ignore[reportUnnecessaryComparison]
            self._recipe.delete()
        if self._repository is not None:  # pyright: ignore[reportUnnecessaryComparison]
            self._repository.delete()

    # endregion
    # region Launchpad interaction wrappers

    def _get_lp_client(self) -> launchpad.Launchpad:
        """Get the launchpad client for the remote builder."""
        credentials_filepath = self.credentials_filepath

        if credentials_filepath.exists():
            craft_cli.emit.debug(
                f"Logging in with credentials file {credentials_filepath}."
            )
        else:
            # the Launchpad class will create a file when the user logs in
            craft_cli.emit.debug(f"Credentials file {credentials_filepath} not found.")

        with craft_cli.emit.pause():
            return launchpad.Launchpad.login(
                f"{self._app.name}/{self._app.version}",
                root=self._services.config.get("launchpad_instance"),
                credentials_file=credentials_filepath,
            )

    def _ensure_project(self) -> launchpad.models.Project:
        """Ensure that the user's remote build project exists."""
        if self._lp_project:
            return self._lp_project
        try:
            return self.lp.get_project(f"{self.lp.username}-craft-remote-build")
        except launchpad.errors.NotFoundError:
            return self.lp.new_project(
                name=f"{self.lp.username}-craft-remote-build",
                title=f"*craft remote builds for {self.lp.username}",
                display_name=f"{self.lp.username} remote builds",
                summary=f"Automatically-generated project for housing {self.lp.username}'s remote builds in snapcraft, charmcraft, etc.",
            )

    def _ensure_repository(
        self, project_dir: pathlib.Path
    ) -> tuple[WorkTree, launchpad.models.GitRepository]:
        """Create a repository on the local machine and ensure it's on Launchpad."""
        work_tree = WorkTree(self._app.name, self._name, project_dir)
        work_tree.init_repo()
        try:
            lp_repository = self.lp.new_repository(
                self._name, project=self._lp_project.name
            )
        except launchpadlib.errors.HTTPError:
            lp_repository = self.lp.get_repository(
                name=self._name, project=self._lp_project.name
            )

        token = lp_repository.get_access_token(
            f"{self._app.name} {self._app.version} remote build",
            expiry=datetime.datetime.now(tz=datetime.timezone.utc)
            + datetime.timedelta(seconds=300),
        )
        repo_url = parse.urlparse(str(lp_repository.git_https_url))
        push_url = repo_url._replace(
            netloc=f"{self.lp.lp.me.name}:{token}@{repo_url.netloc}"  # pyright: ignore[reportOptionalMemberAccess,reportAttributeAccessIssue,reportUnknownMemberType]
        )

        try:
            local_repository = GitRepo(work_tree.repo_dir)
            local_repository.push_url(push_url.geturl(), "main", push_tags=True)
        except GitError as git_error:
            raise RemoteBuildGitError(
                cast(str, git_error.details),
            ) from git_error
        else:
            return work_tree, lp_repository

    def _get_repository(self) -> launchpad.models.GitRepository:
        """Get an existing repository on Launchpad."""
        return self.lp.get_repository(name=self._name, owner=self.lp.username)

    def _ensure_recipe(
        self,
        name: str,
        repository: launchpad.models.GitRepository,
        **kwargs: Any,  # noqa: ANN401
    ) -> launchpad.models.Recipe:
        """Get a recipe or create it if it doesn't exist."""
        with contextlib.suppress(ValueError):  # Recipe doesn't exist
            recipe = self._get_recipe()
            recipe.delete()

        return self._new_recipe(name, repository, **kwargs)

    def _new_recipe(
        self,
        name: str,
        repository: launchpad.models.GitRepository,
        **kwargs: Any,  # noqa: ANN401
    ) -> launchpad.models.Recipe:
        """Create a new recipe for the given repository."""
        repository.lp_refresh()  # Prevents a race condition on new repositories.
        git_ref = parse.urlparse(str(repository.git_https_url)).path + "/+ref/main"

        # if kwargs has a collection of 'architectures',  replace 'all' with 'amd64'
        # because the amd64 runners are fast to build on
        if kwargs.get("architectures"):
            kwargs["architectures"] = [
                "amd64" if arch == "all" else arch for arch in kwargs["architectures"]
            ]

        return self.RecipeClass.new(
            self.lp,
            name,
            self.lp.username,
            git_ref=git_ref,
            project=self._lp_project.name,
            **kwargs,
        )

    def _get_recipe(self) -> launchpad.models.Recipe:
        """Get a build for this application by its build ID.

        If an application's recipe class needs more than just the name and owner,
        this method and new_recipe should be overridden.
        """
        return self.RecipeClass.get(
            self.lp, self._name, self.lp.username, self._lp_project.name
        )

    def _new_builds(
        self, recipe: launchpad.models.Recipe
    ) -> Collection[launchpad.models.Build]:
        """Create a build from a Launchpad repository."""
        return recipe.build(deadline=self._deadline)

    def _get_builds(self) -> Collection[launchpad.models.Build]:
        """Get the builds for a recipe by its name."""
        return self._recipe.get_builds()

    def _get_build_states(self) -> Mapping[str, launchpad.models.BuildState]:
        self._refresh_builds()
        return {build.arch_tag: build.get_state() for build in self._builds}

    def _refresh_builds(self) -> None:
        """Refresh the data for builds from Launchpad."""
        for build in self._builds:
            build.lp_refresh()

    def _get_artifact_urls(self) -> Collection[str]:
        """Get the locations of all build artifacts."""
        return list(
            itertools.chain.from_iterable(
                build.get_artifact_urls() for build in self._builds
            )
        )

    # endregion

    def _check_timeout(self) -> None:
        """Check if we've timed out."""
        if self._deadline is not None and time.monotonic_ns() >= self._deadline:
            raise TimeoutError
