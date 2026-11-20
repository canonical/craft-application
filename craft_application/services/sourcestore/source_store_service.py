#  This file is part of craft-application.
#
#  Copyright 2026 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Service class for Source Store commands."""

from __future__ import annotations

import time
from contextlib import suppress
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, cast
from urllib.parse import urljoin, urlparse

from craft_cli import emit
from craft_store import UbuntuOneStoreClient, endpoints
from craft_store.auth import Auth
from craft_store.creds import DeveloperToken
from craft_store.errors import (
    CraftStoreError,
    CredentialsUnavailable,
    IncorrectPlaneError,
    StoreServerError,
)
from craft_store.models import MarshableModel, Plane
from craft_store.publisher import (
    ORIGIN_REMOTE_NAME,
    STORE_REMOTE_NAME,
    UPSTREAM_REMOTE_NAME,
    Buildset,
    PublisherGateway,
    Releases,
    Remote,
    Revision,
)

from craft_application.errors import (
    CommitNotFoundInRemoteError,
    CommitWorkflowTimeoutError,
    DirtyRepositoryError,
    IncorrectPlaneSpecifiedError,
    OriginUndefinedError,
    ProjectIsNotRepositoryError,
    RepositoryWithoutOriginError,
    StoreRemoteExistsError,
    StoreRemoteUnvailableError,
)
from craft_application.git import (
    Commit,
    GitRepo,
    is_commit,
    is_repo,
    short_commit_sha,
)
from craft_application.services import base
from craft_application.util import get_hostname

from ._environment import ENV_VARS, get_sd_environment
from .auth import (
    build_user_agent,
    get_publisher_gateway_url,
    get_store_login_url,
    get_store_url,
    prompt_login,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from craft_application.application import AppMetadata
    from craft_application.services import ServiceFactory

INVALID_REMOTE_URL = "undefined-remote-url"

DEFAULT_PACKAGES: list[endpoints.Package] = []
DEFAULT_PERMISSIONS: list[str] = [
    "package_access",
    "package_manage",
    "package_metrics",
    "package_push",
    "package_register",
    "package_release",
    "package_update",
]

DEFAULT_TTL: int = int(timedelta(days=365).total_seconds())


class WorkflowData(MarshableModel):
    """Class representing filtered data from a commit workflow response."""

    buildset_id: str
    channel_name: str


class SourceStoreService(base.AppService):
    """Business logic for operation on sourcestore."""

    def __init__(
        self,
        app: AppMetadata,
        services: ServiceFactory,
        *,
        ephemeral_credential_storage: bool = False,
        auth_file_fallback: bool = True,
        namespace: str | None = None,
    ) -> None:
        super().__init__(app, services)
        self._auth_file_fallback = auth_file_fallback
        sd_environment = get_sd_environment()
        env_plane = sd_environment.push_plane
        self._plane = Plane.from_str(env_plane) if env_plane else None
        host = urlparse(get_publisher_gateway_url()).netloc
        self._namespace = namespace or app.name.removesuffix("craft")
        self._credential_storage = Auth(
            application_name=f"{self._app.name}-dev-token",
            host=host,
            ephemeral=ephemeral_credential_storage,
            environment_auth=ENV_VARS.source_store_credentials,
            file_fallback=self._auth_file_fallback,
        )
        self._craft_publisher_gateway = PublisherGateway(
            base_url=get_publisher_gateway_url(),
            namespace=self._namespace,
            auth=self._credential_storage,
            plane=self._plane,
        )

    def register_name(
        self,
        *,
        name: str,
        private: bool,
        entity_type: str | None = None,
    ) -> str:
        """Register new name in store.

        :return: Id of created package.
        """
        entity_type = entity_type or self._namespace
        return self._craft_publisher_gateway.register_name(
            name=name,
            entity_type=entity_type,
            private=private,
        )

    def _get_plane(self, plane: Plane | None) -> Plane | None:
        """Get plane associated with the following requests.

        It starts with checking the user-provided one, fallback
        to environment variable and compares that with the
        underlying git repository if possible.
        """
        plane = plane or self._plane
        if not is_repo(Path.cwd()):
            # if run outside of repository it can't be compared
            if plane:
                emit.debug(f"Using plane {plane.name!r} for the remaining requests")
            return plane

        repository_plane = self.get_plane_from_repository(self._get_git_repo())
        if (plane and repository_plane) and plane != repository_plane:
            raise IncorrectPlaneSpecifiedError(
                plane.name,
                details=f"Provided plane differs from the stored value: {plane.name!r} (provided)"
                f" != {repository_plane.name!r} (stored)",
            )
        plane = plane or repository_plane
        if plane:
            emit.debug(f"Using plane {plane.name!r} for the remaining requests")
        return plane

    def commit(
        self,
        *,
        name: str,
        ref: str | None,
        channel: str,
        plane: Plane | None = None,
        timeout: int = 3600,
        sleep_between_retries: float = 0.5,
    ) -> WorkflowData | None:
        """Create new source revision from commit in origin."""
        plane = self._get_plane(plane)
        if not is_repo(Path.cwd()):
            raise ProjectIsNotRepositoryError(name)

        origin = self.get_origin_if_exists(package_name=name, plane=plane)
        if origin is None:
            raise OriginUndefinedError(
                f"There is no origin associated with {name!r}",
                resolution="Try running 'setup-origin' to define an origin.",
            )

        if ref is None:
            commit = self._get_last_commit(name=name)
            if not self._ask_for_confirmation(commit=commit, channel=channel):
                return None
        elif not is_commit(ref):
            commit = self._find_commit(ref=ref)
            if not self._ask_for_confirmation(commit=commit, channel=channel):
                return None
        else:
            commit = ref

        short_commit = short_commit_sha(commit)
        emit.progress(f"Committing {short_commit!r} to the Store")
        commit_workflow_id = self._craft_publisher_gateway.start_commit_workflow(
            package_name=name,
            commit_hash=commit,
            channel=channel,
            plane=plane,
        )
        emit.trace(f"Commit workflow id: {commit_workflow_id!r}")

        workflow_data = self._monitor_commit_workflow(
            commit_workflow_id=commit_workflow_id,
            package_name=name,
            plane=plane,
            timeout=timeout,
            sleep_between_retries=sleep_between_retries,
        )
        emit.progress(
            f"Committed {short_commit!r} to channel {channel!r}",
            permanent=True,
        )
        emit.debug(f"Buildset id: {workflow_data.buildset_id!r}")
        return workflow_data

    def promote_commit(
        self,
        *,
        name: str,
        source_channel: str,
        plane: Plane,
        timeout: int = 3600,
        sleep_between_retries: float = 0.5,
    ) -> WorkflowData:
        """Promote new source revision from a pre-existing one.

        Unlike standard binary promotion like 'snapcraft promote', this action
        triggers a regular commit workflow from the source that is already in
        the Store, and can be reached at the source channel. If the new buildset
        completes successfully, the commit is then automatically released to the
        next lower risk for the source channel's track.

        :param name: the name of the package to promote
        :param source_channel: the channel containing the commit to promote
        :param plane: the plane to perform the promotion operation
        :param timeout: how long to wait for a commit to complete
        :param sleep_between_retries: how many seconds to wait between workflow checks
        """
        emit.progress(f"Triggering promotion of {source_channel!r} to the Store")
        commit_workflow_id = self._craft_publisher_gateway.start_promotion_workflow(
            package_name=name,
            source_channel=source_channel,
            plane=plane,
        )
        emit.trace(f"Commit workflow id: {commit_workflow_id!r}")

        workflow_data = self._monitor_commit_workflow(
            commit_workflow_id=commit_workflow_id,
            package_name=name,
            plane=plane,
            timeout=timeout,
            sleep_between_retries=sleep_between_retries,
        )
        emit.progress(
            f"Promoted {source_channel!r} to {workflow_data.channel_name!r}",
            permanent=True,
        )
        emit.debug(f"Buildset id: {workflow_data.buildset_id!r}")
        return workflow_data

    def _monitor_commit_workflow(
        self,
        *,
        commit_workflow_id: str,
        package_name: str,
        plane: Plane | None,
        timeout: int,
        sleep_between_retries: float,
    ) -> WorkflowData:
        """Monitor a commit workflow for a time and return workflow data."""
        start_time = datetime.now(timezone.utc)
        end_time = start_time + timedelta(seconds=timeout)
        while True:
            commit_workflows = self._craft_publisher_gateway.get_commit_workflows(
                commit_workflow_id=commit_workflow_id,
                package_name=package_name,
                raise_on_error=True,
                plane=plane,
            )
            if commit_workflows:
                commit_workflow = commit_workflows[0]
                if commit_workflow.buildsets:
                    return WorkflowData(
                        buildset_id=commit_workflow.buildsets[0].entity_id,
                        channel_name=commit_workflow.craft_channel.name,
                    )
            if datetime.now(timezone.utc) > end_time:
                raise CommitWorkflowTimeoutError(
                    f"Commit for {package_name!r} didn't finish in the expected time",
                )
            time.sleep(sleep_between_retries)

    def _ask_for_confirmation(self, *, commit: str, channel: str) -> bool:
        short_commit = short_commit_sha(commit)
        emit.debug(
            f"Prompting for release confirmation of {short_commit!r} on {channel!r}"
        )
        return cast(
            bool,
            emit.confirm(
                f"\nDo you want to release {short_commit!r} to {channel!r} ?",
                default=False,
            ),
        )

    def _git_url_with_credentials(self, store_remote_url: str) -> str:
        git_url = store_remote_url

        prefix = "https://"

        if not git_url.startswith(prefix):
            emit.debug("Credentials only support HTTPS. Skipping authentication...")
            return git_url

        dev_token = DeveloperToken.model_validate_json(
            self._credential_storage.get_credentials()
        )
        macaroon = dev_token.macaroon
        emit.set_secrets([macaroon])

        return f"{prefix}{self.clone_user}:{macaroon}@{git_url[len(prefix) :]}"

    @property
    def clone_user(self) -> str:
        """Return user used to clone repository."""
        return "craft"

    @property
    def _repository_plane_key(self) -> str:
        return "craft.plane"

    def set_plane_in_repository(self, repo: GitRepo, plane: Plane | None) -> None:
        """Add plane to the local repository configuration."""
        if plane is None:
            return
        emit.debug(f"Setting plane in repository to {plane.name!r}")
        repo.set_config_value(self._repository_plane_key, plane.name)

    def get_plane_from_repository(self, repo: GitRepo) -> Plane | None:
        """Get plane from the local repository configuration."""
        plane_str = repo.get_config_value(self._repository_plane_key)
        if plane_str is None:
            return None
        try:
            return Plane.from_str(plane_str)
        except IncorrectPlaneError:
            emit.debug(f"Cannot read plane from repository: {plane_str!r}")
        return None

    def clone(
        self,
        *,
        name: str,
        cloning_path: Path,
        channel: str,
        plane: Plane | None,
    ) -> None:
        """Clone source package from given release."""
        remotes = self.get_remotes(package_name=name, channel=channel, plane=plane)
        store_remote = _get_store_repository(remotes, package_name=name)
        origin = _get_origin_if_exists(remotes)
        parsed_channel = _parse_channel(channel)

        git_url = self._git_url_with_credentials(store_remote.url)

        emit.progress(
            f"Cloning sources from Source Store (branch: {parsed_channel!r})",
        )
        repo = GitRepo.clone_repository(
            url=git_url,
            path=cloning_path,
            checkout_branch=parsed_channel,
        )

        emit.trace("Updating remote URL to remove credentials")
        repo.set_remote_url(ORIGIN_REMOTE_NAME, store_remote.url)

        self.set_plane_in_repository(repo, plane)

        repo.rename_remote(ORIGIN_REMOTE_NAME, STORE_REMOTE_NAME)
        repo.set_no_push(STORE_REMOTE_NAME)
        if origin is not None:
            emit.progress(
                f"Setting {ORIGIN_REMOTE_NAME!r} to {origin.url!r}",
            )
            repo.add_remote(ORIGIN_REMOTE_NAME, origin.url)
        else:
            emit.debug("Origin not available, skipping...")

        upstream_repository = _get_upstream_if_exists(remotes)
        if (
            upstream_repository is not None
            and upstream_repository.url != INVALID_REMOTE_URL
        ):
            emit.progress(
                f"Setting {UPSTREAM_REMOTE_NAME!r} to {upstream_repository.url!r}",
            )
            repo.add_remote(UPSTREAM_REMOTE_NAME, upstream_repository.url)
            repo.set_no_push(UPSTREAM_REMOTE_NAME)

    def setup_origin(
        self,
        *,
        package_name: str,
        plane: Plane | None,
        create: bool = False,
        external: bool = False,
        requires_pat: bool = False,
    ) -> None:
        """Enable source store support for the given craft project.

        :param package_name: the name of the package in the source store.
        :param plane: the source store plane to which this will be added.
        :param create: request new origin from the source store.
        :param external: configure the source store to use the local origin.
        """
        if create:
            raise NotImplementedError("Cannot request origin yet")

        if external:
            self._setup_external_origin(
                package_name=package_name, plane=plane, requires_pat=requires_pat
            )

    def _setup_external_origin(
        self,
        *,
        package_name: str,
        plane: Plane | None,
        requires_pat: bool = False,
    ) -> None:
        """Set the source store repository, pointing store to the existing origin."""
        repository_path = Path.cwd()
        if not is_repo(repository_path):
            raise ProjectIsNotRepositoryError(package_name)
        git_repo = self._get_git_repo(repository_path=repository_path)

        if not git_repo.remote_exists(ORIGIN_REMOTE_NAME):
            raise RepositoryWithoutOriginError(package_name)

        if git_repo.remote_exists(STORE_REMOTE_NAME):
            raise StoreRemoteExistsError(package_name)

        origin_url = git_repo.get_remote_url(ORIGIN_REMOTE_NAME)
        access_token: str | None = None
        if requires_pat:
            access_token = emit.prompt(
                f"Personal Access Token for {origin_url!r}: ", hide=True
            )
        emit.debug(f"Setting {ORIGIN_REMOTE_NAME!r} in source store to {origin_url!r}")
        self._craft_publisher_gateway.update_remote(
            action="setup",
            package_name=package_name,
            remote_name=ORIGIN_REMOTE_NAME,
            remote_type="external",
            access_token=access_token,
            url=origin_url,
            plane=plane,
        )

        try:
            store_repository = self.get_store_repository(
                package_name=package_name,
                plane=plane,
            )
        except StoreRemoteUnvailableError:
            emit.debug(f"Store hasn't returned requested remote: {STORE_REMOTE_NAME!r}")
            raise
        else:
            git_repo.add_remote(STORE_REMOTE_NAME, store_repository.url)
            git_repo.set_no_push(STORE_REMOTE_NAME)

        self.set_plane_in_repository(git_repo, plane)

    def get_origin_if_exists(
        self,
        *,
        package_name: str,
        plane: Plane | None,
    ) -> Remote | None:
        """Get default origin for selected package."""
        remotes = self.get_remotes(package_name=package_name, plane=plane)
        return _get_origin_if_exists(remotes)

    def get_upstream_if_exists(
        self,
        *,
        package_name: str,
        plane: Plane | None,
    ) -> Remote | None:
        """Get upstream repository for selected package."""
        remotes = self.get_remotes(package_name=package_name, plane=plane)
        return _get_upstream_if_exists(remotes)

    def get_store_repository(
        self,
        *,
        package_name: str,
        plane: Plane | None,
        channel: str | None = None,
    ) -> Remote:
        """Get store repository for selected package."""
        remotes = self.get_remotes(
            package_name=package_name, plane=plane, channel=channel
        )
        return _get_store_repository(remotes, package_name=package_name)

    def get_remotes(
        self,
        *,
        package_name: str,
        plane: Plane | None,
        channel: str | None = None,
    ) -> list[Remote]:
        """Get all remote repositories for selected package."""
        plane = self._get_plane(plane)
        return self._craft_publisher_gateway.get_remotes(
            package_name=package_name, channel=channel, plane=plane
        )

    def login(
        self,
        *,
        ttl: int = DEFAULT_TTL,
        packages: list[endpoints.Package] | None = None,
        permissions: list[str] | None = None,
    ) -> None:
        """Login into the store and store the credentials."""
        self._credential_storage.ensure_no_credentials()

        store_client = get_store_client(
            self._app.name, self._app.version, file_fallback=self._auth_file_fallback
        )
        desc = f"{self._app.name}@{get_hostname()}"
        login, password = prompt_login()

        if packages is None:
            packages = DEFAULT_PACKAGES

        if permissions is None:
            permissions = DEFAULT_PERMISSIONS

        try:
            store_client.login(
                ttl=ttl,
                email=login,
                password=password,
                description=desc,
                permissions=permissions,
                packages=packages,
            )
        except StoreServerError as store_error:
            if "twofactor-required" not in store_error.error_list:
                raise
            otp = emit.prompt("Second-factor auth: ")
            store_client.login(
                ttl=ttl,
                email=login,
                password=password,
                description=desc,
                permissions=permissions,
                packages=packages,
                otp=otp,
            )
        self._get_developer_token(store_client)

    def _get_developer_token(self, store_client: UbuntuOneStoreClient) -> None:
        self._credential_storage.ensure_no_credentials()
        dev_token_response = store_client.request(
            "POST",
            _get_developer_gateway_endpoint(),
            json=endpoints.SOURCESTORE_DEVELOPER_TOKEN_ENDPOINTS.get_token_request(),
        )
        dev_token = DeveloperToken.unmarshal(dev_token_response.json())

        self._credential_storage.set_credentials(dev_token.model_dump_json())

    def logout(self) -> None:
        """Remove stored credentials."""
        with suppress(CredentialsUnavailable):
            self._credential_storage.del_credentials()
        store_client = get_store_client(
            self._app.name, self._app.version, file_fallback=self._auth_file_fallback
        )
        store_client.logout()

    def get_buildsets(
        self,
        *,
        package_name: str,
        channel: str | None = None,
        commit_hash: str | None = None,
        buildset_id: str | None = None,
        plane: Plane | None = None,
    ) -> list[Buildset]:
        """Get the status of the Buildset from the gateway."""
        plane = self._get_plane(plane)
        return self._craft_publisher_gateway.get_buildsets(
            package_name=package_name,
            buildset_id=buildset_id,
            channel=channel,
            commit_hash=commit_hash,
            plane=plane,
        )

    def create_buildset(
        self,
        *,
        package_name: str,
        channel: str,
        plane: Plane | None = None,
    ) -> list[str]:
        """Create a new buildset of the released Source Store channel."""
        plane = self._get_plane(plane)
        return [
            buildset.buildset_id
            for buildset in self._craft_publisher_gateway.create_buildset(
                package_name=package_name,
                plane=plane,
                channel=channel,
            )
        ]

    def download_logs(
        self,
        *,
        package_name: str,
        buildset_id: str,
        dest_dir: Path,
        plane: Plane | None = None,
    ) -> dict[str, list[Path]]:
        """Download all the logs currently available for the buildset.

        Returns a dict where the key is a build architecture and the value is a list
        of log files downloaded from that build.
        """

        @dataclass
        class ToDownload:
            url: str
            file_suffix: str

        plane = self._get_plane(plane)

        buildsets = self._craft_publisher_gateway.get_buildsets(
            package_name=package_name,
            buildset_id=buildset_id,
            plane=plane,
        )
        buildset = buildsets[0]
        to_download: dict[str, list[ToDownload]] = {}
        downloaded: dict[str, list[Path]] = {}

        for build in buildset.builds:
            arch = build.platform.architectures[0]
            build_log = build.logs.build_log_download_url
            fetch_service_report = build.logs.fetch_service_metadata_download_url
            logs: list[ToDownload] = []
            if build_log:
                logs.append(ToDownload(str(build_log), "build.txt"))
            if fetch_service_report:
                logs.append(ToDownload(str(fetch_service_report), "report.json"))
            if logs:
                to_download[arch] = logs

        for arch, logs in to_download.items():
            emit.progress(f"Downloading logs for {arch!r}")
            arch_logs: list[Path] = []
            for log in logs:
                dest_path = dest_dir / f"{buildset_id}-{arch}-{log.file_suffix}"
                try:
                    self._download(log.url, dest_path)
                except CraftStoreError as err:
                    emit.debug(f"Failed to download log from {log.url!r}: {err!r}")
                else:
                    arch_logs.append(dest_path)
            if arch_logs:
                downloaded[arch] = arch_logs

        return downloaded

    def list_revisions(
        self,
        *,
        package_name: str,
        fields: list[str] | None = None,
        include_craft_yaml: bool = False,
        revision: int | None = None,
    ) -> Sequence[Revision]:
        """List all binary revisions for the given package."""
        fields = fields or [
            "revision",
            "size",
            "status",
            "version",
            "created-at",
            "craft",
        ]
        return self._craft_publisher_gateway.list_revisions(
            package_name,
            fields=fields,
            include_craft_yaml=include_craft_yaml,
            revision=revision,
        )

    def list_releases(
        self,
        *,
        package_name: str,
    ) -> Releases:
        """List all binary revisions for the given package."""
        return self._craft_publisher_gateway.list_releases(
            package_name,
        )

    def _get_last_commit(self, *, name: str) -> str:
        """Find last commit in the current dir."""
        git_repo = self._get_git_repo()
        if not git_repo.is_clean():
            raise DirtyRepositoryError(name=name, remote=ORIGIN_REMOTE_NAME)
        last_commit = git_repo.get_last_commit()
        emit.debug(
            f"Using last commit from the current branch {last_commit.short_sha!r}"
        )
        self._check_and_print(git_repo, last_commit)
        return last_commit.sha

    def _find_commit(self, *, ref: str) -> str:
        """Find commit sha based on provided ref (tag or branch)."""
        git_repo = self._get_git_repo()
        found_commit = git_repo.get_last_commit_on_branch_or_tag(
            remote=ORIGIN_REMOTE_NAME,
            branch_or_tag=ref,
            fetch=True,
        )
        emit.debug(
            f"Using commit {found_commit.short_sha!r} associated with the given ref {ref!r}"
        )
        self._check_and_print(git_repo, found_commit)
        return found_commit.sha

    def _check_and_print(self, git_repo: GitRepo, commit: Commit) -> None:
        if not git_repo.remote_contains(
            remote=ORIGIN_REMOTE_NAME, commit_sha=commit.sha
        ):
            raise CommitNotFoundInRemoteError(commit.short_sha, ORIGIN_REMOTE_NAME)
        print_commit(commit)

    def _get_git_repo(self, *, repository_path: Path | None = None) -> GitRepo:
        """Get GitRepo object for the given path or current working directory."""
        if repository_path is None:
            repository_path = Path.cwd()
        return GitRepo(repository_path)

    def _download(self, url: str, dest_path: Path) -> None:
        """Download file from given URL to the destination path."""
        response = self._craft_publisher_gateway.get(url=url)
        dest_path.write_bytes(response.content)


def _get_developer_gateway_endpoint() -> str:
    return urljoin(
        get_publisher_gateway_url(),
        endpoints.SOURCESTORE_DEVELOPER_TOKEN_ENDPOINTS.tokens_exchange,
    )


def get_store_client(
    app_name: str,
    app_version: str,
    *,
    file_fallback: bool,
) -> UbuntuOneStoreClient:
    """Get store client used to login and retrieve developer token."""
    return UbuntuOneStoreClient(
        application_name=app_name,
        endpoints=endpoints.U1_SNAP_STORE,
        base_url=get_store_url(),
        auth_url=get_store_login_url(),
        storage_base_url="",
        user_agent=build_user_agent(app_name=app_name, version=app_version),
        environment_auth=None,  # Currently env-based SSO auth is not supported
        file_fallback=file_fallback,
    )


def _parse_channel(channel: str) -> str:
    """Parse channel to the git-branch."""
    return channel.replace("/", "_")


def print_commit(commit: Commit) -> None:
    """Print commit summary to the user."""
    emit.progress(
        f"commit:\t{commit.sha}",
        permanent=True,
    )
    emit.progress(
        f"{commit.message}",
        permanent=True,
    )


def _get_origin_if_exists(
    remotes: list[Remote],
) -> Remote | None:
    """Get default origin for selected package."""
    for remote in remotes:
        if remote.name == ORIGIN_REMOTE_NAME and remote.remote_type in (
            "external",
            "managed",
        ):
            return remote
    return None


def _get_upstream_if_exists(
    remotes: list[Remote],
) -> Remote | None:
    """Get upstream repository for selected package."""
    for remote in remotes:
        if remote.name == UPSTREAM_REMOTE_NAME and remote.remote_type == "external":
            return remote
    return None


def _get_store_repository(
    remotes: list[Remote],
    *,
    package_name: str,
) -> Remote:
    """Get store repository for selected package."""
    for remote in remotes:
        if remote.name == STORE_REMOTE_NAME and remote.remote_type == "store":
            return remote
    raise StoreRemoteUnvailableError(package_name)
