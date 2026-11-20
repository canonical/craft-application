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
"""Unit tests for the SourceStoreService."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, call

import craft_cli
import pytest
import pytest_mock
import pytest_subprocess
from craft_application import models
from craft_application.errors import (
    CommitNotFoundInRemoteError,
    CommitWorkflowTimeoutError,
    IncorrectPlaneSpecifiedError,
)
from craft_application.git import GitRepo, short_commit_sha
from craft_application.services.sourcestore import SourceStoreService
from craft_cli.pytest_plugin import RecordingEmitter
from craft_store.models import Plane
from craft_store.publisher import (
    ORIGIN_REMOTE_NAME,
    Channel,
    CommitWorkflow,
    Error,
    Remote,
    SourceStoreOperationStatus,
    StoreEntityReference,
)


@pytest.fixture
def last_commit_msg() -> str:
    return "chore: create test commit"


@pytest.fixture
def project_dir(
    empty_project_dir: Path,
    project_yaml_path: Path,
    fake_project: models.Project,
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.chdir(empty_project_dir)
    fake_project.to_yaml_file(project_yaml_path)
    return empty_project_dir


@pytest.fixture
def project_dir_git_repository(
    project_dir: Path,
    last_commit_msg: str,
):
    repo_path = project_dir
    git_repo = GitRepo(repo_path)
    git_repo.add_all()
    git_repo.commit(last_commit_msg)
    return repo_path


@pytest.fixture
def stored_plane(
    source_store: SourceStoreService, project_dir_git_repository: Path
) -> Plane:
    plane = Plane.from_str("another/plane")
    git_repo = GitRepo(project_dir_git_repository)
    git_repo.set_config_value(source_store._repository_plane_key, plane.name)
    return plane


@pytest.fixture
def fake_commit_sha() -> str:
    return "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


@pytest.fixture
def patched_get_origin(
    source_store: SourceStoreService,
    fake_origin: Remote,
    mocker: pytest_mock.MockerFixture,
) -> None:
    mocker.patch.object(source_store, "get_origin_if_exists", return_value=fake_origin)


def get_commit_workflow(
    *,
    commit_id: str = "test-commit-id",
    commit_hash: str = "commit-123",
    created_at: datetime,
    completed_at: datetime | None,
    craft_channel: Channel | None = None,
    error_list: list[Error] | None = None,
    buildsets: list[StoreEntityReference] | None = None,
    status: SourceStoreOperationStatus = SourceStoreOperationStatus.SUCCEEDED,
) -> CommitWorkflow:
    craft_channel = craft_channel or Channel(
        track="test", risk="edge", name="test/edge"
    )
    if buildsets is None:
        buildsets = [
            StoreEntityReference(
                entity_id="fake-buildset-id-978",
            )
        ]
    if error_list is None:
        error_list = []

    return CommitWorkflow(
        commit_id=commit_id,
        commit_hash=commit_hash,
        created_at=created_at,
        completed_at=completed_at,
        craft_channel=craft_channel,
        error_list=error_list,
        buildsets=buildsets,
        status=status,
    )


def _commit_check_command(git_command: str, commit_sha: str) -> list[str]:
    return [
        git_command,
        "branch",
        "--color=never",
        "--column=never",
        "--remotes",
        "--contains",
        commit_sha,
    ]


@pytest.fixture
def fake_commit_workflow(craft_publisher_gw_client_mock: MagicMock) -> CommitWorkflow:
    created_at = datetime.now(timezone.utc)
    completed_at = created_at - timedelta(minutes=3, seconds=23)
    commit_workflow = get_commit_workflow(
        created_at=created_at, completed_at=completed_at
    )
    craft_publisher_gw_client_mock.get_commit_workflows.return_value = [commit_workflow]
    return commit_workflow


@pytest.mark.usefixtures("patched_get_origin")
def test_commit_non_interactive(
    source_store: SourceStoreService,
    fake_project: models.Project,
    fake_commit_sha: str,
    craft_publisher_gw_client_mock: MagicMock,
    fake_commit_workflow: CommitWorkflow,
    emitter: RecordingEmitter,
) -> None:
    project_name = fake_project.name
    fake_commit_workflow_id = "commit-workflow-id-213"
    craft_publisher_gw_client_mock.start_commit_workflow.return_value = (
        fake_commit_workflow_id
    )

    triggered_buildset_id = fake_commit_workflow.buildsets[0].entity_id

    source_store.commit(
        name=project_name,
        ref=fake_commit_sha,
        channel="test/edge",
    )
    craft_publisher_gw_client_mock.start_commit_workflow.assert_called_with(
        commit_hash=fake_commit_sha,
        channel="test/edge",
        package_name=project_name,
        plane=source_store._plane,
    )

    short_commit = short_commit_sha(fake_commit_sha)
    emitter.assert_interactions(
        [
            call(
                "progress",
                f"Committing {short_commit!r} to the Store",
            ),
            call(
                "trace",
                f"Commit workflow id: {fake_commit_workflow_id!r}",
            ),
            call(
                "progress",
                f"Committed {short_commit!r} to channel {'test/edge'!r}",
                permanent=True,
            ),
            call(
                "debug",
                f"Buildset id: {triggered_buildset_id!r}",
            ),
        ]
    )


@pytest.fixture
def patched_emit_confirm(
    mocker: pytest_mock.MockFixture,
) -> pytest_mock.MockType:
    return mocker.patch.object(
        craft_cli.emit,
        "confirm",
        return_value=True,
    )


@pytest.mark.usefixtures("patched_get_origin")
def test_commit_last_commit_in_the_current_workspace(
    source_store: SourceStoreService,
    fake_project: models.Project,
    craft_publisher_gw_client_mock: MagicMock,
    emitter: RecordingEmitter,
    fake_process: pytest_subprocess.FakeProcess,
    project_dir_git_repository: Path,
    mocker: pytest_mock.MockFixture,
    last_commit_msg: str,
    expected_git_command: str,
    patched_emit_confirm: pytest_mock.MockType,
    fake_commit_workflow: CommitWorkflow,
) -> None:
    project_name = fake_project.name
    commit_workflow_id = "fake-release-id-123"
    craft_publisher_gw_client_mock.start_commit_workflow.return_value = (
        commit_workflow_id
    )
    buildset_id = fake_commit_workflow.buildsets[0].entity_id
    git_repo = GitRepo(project_dir_git_repository)
    last_commit = git_repo.get_last_commit()
    fake_process.register(
        _commit_check_command(expected_git_command, last_commit.sha),
        stdout=f"{ORIGIN_REMOTE_NAME}/some-branch",
    )

    # Run the service API
    source_store.commit(
        name=project_name,
        channel="test/edge",
        ref=None,
    )
    craft_publisher_gw_client_mock.start_commit_workflow.assert_called_with(
        commit_hash=last_commit.sha,
        channel="test/edge",
        package_name=project_name,
        plane=source_store._plane,
    )

    patched_emit_confirm.assert_called()

    emitter.assert_interactions(
        [
            call(
                "debug",
                f"Using last commit from the current branch {last_commit.short_sha!r}",
            ),
            call(
                "progress",
                f"commit:\t{last_commit.sha}",
                permanent=True,
            ),
            call(
                "progress",
                last_commit_msg,
                permanent=True,
            ),
            call(
                "debug",
                f"Prompting for release confirmation of {last_commit.short_sha!r} on {'test/edge'!r}",
            ),
            call(
                "progress",
                f"Committing {last_commit.short_sha!r} to the Store",
            ),
            call(
                "trace",
                f"Commit workflow id: {commit_workflow_id!r}",
            ),
            call(
                "progress",
                f"Committed {last_commit.short_sha!r} to channel {'test/edge'!r}",
                permanent=True,
            ),
            call(
                "debug",
                f"Buildset id: {buildset_id!r}",
            ),
        ]
    )


@pytest.mark.usefixtures("patched_get_origin")
def test_commit_last_commit_not_confirmed_by_user(
    source_store: SourceStoreService,
    fake_project: models.Project,
    emitter: RecordingEmitter,
    fake_process: pytest_subprocess.FakeProcess,
    project_dir_git_repository: Path,
    mocker: pytest_mock.MockFixture,
    last_commit_msg: str,
    expected_git_command: str,
    patched_emit_confirm: pytest_mock.MockType,
    craft_publisher_gw_client_mock: MagicMock,
) -> None:
    project_name = fake_project.name
    commit_workflow_id = "commit-workflow-id-123"
    craft_publisher_gw_client_mock.start_commit_workflow.return_value = (
        commit_workflow_id
    )
    git_repo = GitRepo(project_dir_git_repository)
    last_commit = git_repo.get_last_commit()
    fake_process.register(
        _commit_check_command(expected_git_command, last_commit.sha),
        stdout=f"{ORIGIN_REMOTE_NAME}/some-branch",
    )
    patched_emit_confirm.return_value = False

    # Run the service API
    source_store.commit(
        name=project_name,
        channel="test/edge",
        ref=None,
    )
    craft_publisher_gw_client_mock.start_commit_workflow.assert_not_called()
    patched_emit_confirm.assert_called()

    emitter.assert_interactions(
        [
            call(
                "debug",
                f"Using last commit from the current branch {last_commit.short_sha!r}",
            ),
            call(
                "progress",
                f"commit:\t{last_commit.sha}",
                permanent=True,
            ),
            call(
                "progress",
                last_commit_msg,
                permanent=True,
            ),
            call(
                "debug",
                f"Prompting for release confirmation of {last_commit.short_sha!r} on {'test/edge'!r}",
            ),
        ]
    )


@pytest.mark.usefixtures("patched_get_origin")
def test_commit_last_commit_not_pushed(
    source_store: SourceStoreService,
    fake_project: models.Project,
    emitter: RecordingEmitter,
    fake_process: pytest_subprocess.FakeProcess,
    project_dir_git_repository: Path,
    expected_git_command: str,
    craft_publisher_gw_client_mock: MagicMock,
) -> None:
    project_name = fake_project.name
    git_repo = GitRepo(project_dir_git_repository)
    last_commit = git_repo.get_last_commit()
    fake_process.register(
        _commit_check_command(expected_git_command, last_commit.sha),
        stdout="",
    )

    with pytest.raises(CommitNotFoundInRemoteError):
        # Run the service API
        source_store.commit(
            name=project_name,
            channel="test/edge",
            ref=None,
        )
    craft_publisher_gw_client_mock.start_commit_workflow.assert_not_called()

    emitter.assert_interactions(
        [
            call(
                "debug",
                f"Using last commit from the current branch {last_commit.short_sha!r}",
            ),
        ]
    )


@pytest.mark.usefixtures("patched_get_origin")
def test_commit_discovery(
    source_store: SourceStoreService,
    fake_project: models.Project,
    emitter: RecordingEmitter,
    fake_process: pytest_subprocess.FakeProcess,
    project_dir_git_repository: Path,
    mocker: pytest_mock.MockFixture,
    last_commit_msg: str,
    expected_git_command: str,
    patched_emit_confirm: pytest_mock.MockType,
    craft_publisher_gw_client_mock: MagicMock,
    fake_commit_workflow: CommitWorkflow,
) -> None:
    project_name = fake_project.name
    commit_workflow_id = "fake-commit-workflow-id-123"
    ref_branch_or_tag = "test-branch"
    craft_publisher_gw_client_mock.start_commit_workflow.return_value = (
        commit_workflow_id
    )
    git_repo = GitRepo(project_dir_git_repository)
    git_repo.add_remote(ORIGIN_REMOTE_NAME, "https://fake.remote.localhost")
    last_commit = git_repo.get_last_commit()
    fake_process.register(
        _commit_check_command(expected_git_command, last_commit.sha),
        stdout=f"{ORIGIN_REMOTE_NAME}/some-branch",
    )
    fake_process.register(
        [expected_git_command, "fetch", "--tags", ORIGIN_REMOTE_NAME],
    )
    fake_process.register(
        [expected_git_command, "rev-list", "-n", "1", ref_branch_or_tag],
        stdout=last_commit.sha,
    )

    # Run the service API
    source_store.commit(
        name=project_name,
        channel="test/edge",
        ref=ref_branch_or_tag,
    )

    patched_emit_confirm.assert_called()

    craft_publisher_gw_client_mock.start_commit_workflow.assert_called_with(
        channel="test/edge",
        commit_hash=last_commit.sha,
        package_name=project_name,
        plane=source_store._plane,
    )

    emitter.assert_interactions(
        [
            call(
                "debug",
                f"Using commit {last_commit.short_sha!r} associated with the given ref {ref_branch_or_tag!r}",
            ),
            call(
                "progress",
                f"commit:\t{last_commit.sha}",
                permanent=True,
            ),
            call(
                "progress",
                last_commit_msg,
                permanent=True,
            ),
            call(
                "debug",
                f"Prompting for release confirmation of {last_commit.short_sha!r} on {'test/edge'!r}",
            ),
        ]
    )


@pytest.mark.usefixtures("patched_get_origin")
def test_commit_discovery_not_confirmed_by_user(
    source_store: SourceStoreService,
    fake_project: models.Project,
    emitter: RecordingEmitter,
    fake_process: pytest_subprocess.FakeProcess,
    project_dir_git_repository: Path,
    mocker: pytest_mock.MockFixture,
    last_commit_msg: str,
    expected_git_command: str,
    patched_emit_confirm: pytest_mock.MockType,
    craft_publisher_gw_client_mock: MagicMock,
) -> None:
    project_name = fake_project.name
    ref_branch_or_tag = "test-branch"
    git_repo = GitRepo(project_dir_git_repository)
    git_repo.add_remote(ORIGIN_REMOTE_NAME, "https://fake.remote.localhost")
    last_commit = git_repo.get_last_commit()
    fake_process.register(
        _commit_check_command(expected_git_command, last_commit.sha),
        stdout=f"{ORIGIN_REMOTE_NAME}/some-branch",
    )
    fake_process.register(
        [expected_git_command, "fetch", "--tags", ORIGIN_REMOTE_NAME],
    )
    fake_process.register(
        [expected_git_command, "rev-list", "-n", "1", ref_branch_or_tag],
        stdout=last_commit.sha,
    )
    patched_emit_confirm.return_value = False

    # Run the service API
    source_store.commit(
        name=project_name,
        channel="test/edge",
        ref=ref_branch_or_tag,
    )
    craft_publisher_gw_client_mock.start_commit_workflow.assert_not_called()

    patched_emit_confirm.assert_called()
    emitter.assert_interactions(
        [
            call(
                "debug",
                f"Using commit {last_commit.short_sha!r} associated with the given ref {ref_branch_or_tag!r}",
            ),
            call(
                "progress",
                f"commit:\t{last_commit.sha}",
                permanent=True,
            ),
            call(
                "progress",
                last_commit_msg,
                permanent=True,
            ),
            call(
                "debug",
                f"Prompting for release confirmation of {last_commit.short_sha!r} on {'test/edge'!r}",
            ),
        ]
    )


@pytest.mark.usefixtures("patched_get_origin")
def test_commit_wait_for_operation_to_finish(
    source_store: SourceStoreService,
    fake_project: models.Project,
    fake_commit_sha: str,
    craft_publisher_gw_client_mock: MagicMock,
    default_plane: Plane | None,
    emitter: RecordingEmitter,
) -> None:
    project_name = fake_project.name
    fake_commit_workflow_id = "commit-workflow-id-213"
    craft_publisher_gw_client_mock.start_commit_workflow.return_value = (
        fake_commit_workflow_id
    )
    created_at = datetime.now(timezone.utc)
    completed_at = created_at + timedelta(minutes=14, seconds=32)

    craft_publisher_gw_client_mock.get_commit_workflows.side_effect = [
        [
            get_commit_workflow(
                commit_id=fake_commit_workflow_id,
                status=SourceStoreOperationStatus.WAITING,
                created_at=created_at,
                completed_at=None,
                buildsets=[],
            ),
        ],
        [
            get_commit_workflow(
                commit_id=fake_commit_workflow_id,
                status=SourceStoreOperationStatus.RUNNING,
                created_at=created_at,
                completed_at=None,
                buildsets=[],
            ),
        ],
        [
            get_commit_workflow(
                commit_id=fake_commit_workflow_id,
                status=SourceStoreOperationStatus.SUCCEEDED,
                created_at=created_at,
                completed_at=completed_at,
            ),
        ],
    ]

    source_store.commit(
        name=project_name,
        ref=fake_commit_sha,
        channel="test/edge",
        plane=default_plane,
        sleep_between_retries=0.01,
    )
    craft_publisher_gw_client_mock.start_commit_workflow.assert_called_with(
        commit_hash=fake_commit_sha,
        channel="test/edge",
        package_name=project_name,
        plane=default_plane or source_store._plane,
    )

    assert craft_publisher_gw_client_mock.get_commit_workflows.mock_calls == [
        call(
            commit_workflow_id=fake_commit_workflow_id,
            package_name=project_name,
            plane=default_plane or source_store._plane,
            raise_on_error=True,
        ),
        call(
            commit_workflow_id=fake_commit_workflow_id,
            package_name=project_name,
            raise_on_error=True,
            plane=default_plane or source_store._plane,
        ),
        call(
            commit_workflow_id=fake_commit_workflow_id,
            package_name=project_name,
            raise_on_error=True,
            plane=default_plane or source_store._plane,
        ),
    ]

    short_commit = short_commit_sha(fake_commit_sha)
    emitter.assert_interactions(
        [
            call(
                "progress",
                f"Committing {short_commit!r} to the Store",
            ),
            call(
                "trace",
                f"Commit workflow id: {fake_commit_workflow_id!r}",
            ),
            call(
                "progress",
                f"Committed {short_commit!r} to channel {'test/edge'!r}",
                permanent=True,
            ),
        ]
    )


@pytest.mark.usefixtures("patched_get_origin")
def test_commit_timeout(
    source_store: SourceStoreService,
    fake_project: models.Project,
    fake_commit_sha: str,
    craft_publisher_gw_client_mock: MagicMock,
    default_plane: Plane | None,
    emitter: RecordingEmitter,
) -> None:
    project_name = fake_project.name
    fake_commit_workflow_id = "commit-workflow-id-213"
    craft_publisher_gw_client_mock.start_commit_workflow.return_value = (
        fake_commit_workflow_id
    )
    created_at = datetime.now(timezone.utc)

    craft_publisher_gw_client_mock.get_commit_workflows.side_effect = [
        [
            get_commit_workflow(
                commit_id=fake_commit_workflow_id,
                status=SourceStoreOperationStatus.WAITING,
                created_at=created_at,
                completed_at=None,
                buildsets=[],
            ),
        ],
        [
            get_commit_workflow(
                commit_id=fake_commit_workflow_id,
                status=SourceStoreOperationStatus.RUNNING,
                created_at=created_at,
                completed_at=None,
                buildsets=[],
            ),
        ],
    ]

    with pytest.raises(
        CommitWorkflowTimeoutError,
        match=f"Commit for {project_name!r} didn't finish in the expected time",
    ):
        source_store.commit(
            name=project_name,
            ref=fake_commit_sha,
            channel="test/edge",
            sleep_between_retries=0.01,
            plane=default_plane,
            timeout=0,  # fail after 1st request
        )
    craft_publisher_gw_client_mock.start_commit_workflow.assert_called_with(
        commit_hash=fake_commit_sha,
        channel="test/edge",
        package_name=project_name,
        plane=default_plane or source_store._plane,
    )

    assert craft_publisher_gw_client_mock.get_commit_workflows.mock_calls == [
        call(
            commit_workflow_id=fake_commit_workflow_id,
            package_name=project_name,
            raise_on_error=True,
            plane=default_plane or source_store._plane,
        ),
    ]

    short_commit = short_commit_sha(fake_commit_sha)
    emitter.assert_interactions(
        [
            call(
                "progress",
                f"Committing {short_commit!r} to the Store",
            ),
            call(
                "trace",
                f"Commit workflow id: {fake_commit_workflow_id!r}",
            ),
        ]
    )


@pytest.mark.usefixtures("patched_get_origin")
@pytest.mark.parametrize(
    "user_provided_plane",
    [True, False],
    ids=["provided_via_cli", "read_from_repository"],
)
def test_commit_uses_stored_plane(
    source_store: SourceStoreService,
    fake_project: models.Project,
    fake_commit_sha: str,
    craft_publisher_gw_client_mock: MagicMock,
    fake_commit_workflow: CommitWorkflow,
    stored_plane: Plane,
    emitter: RecordingEmitter,
    *,
    user_provided_plane: bool,
) -> None:
    project_name = fake_project.name
    fake_commit_workflow_id = "commit-workflow-id-213"
    craft_publisher_gw_client_mock.start_commit_workflow.return_value = (
        fake_commit_workflow_id
    )

    triggered_buildset_id = fake_commit_workflow.buildsets[0].entity_id
    extra_args = {}
    if user_provided_plane:
        extra_args["plane"] = stored_plane

    source_store.commit(
        name=project_name,
        ref=fake_commit_sha,
        channel="test/edge",
        **extra_args,  # ty: ignore[invalid-argument-type]
    )
    craft_publisher_gw_client_mock.start_commit_workflow.assert_called_with(
        commit_hash=fake_commit_sha,
        channel="test/edge",
        package_name=project_name,
        plane=stored_plane,
    )

    short_commit = short_commit_sha(fake_commit_sha)
    emitter.assert_interactions(
        [
            call(
                "progress",
                f"Committing {short_commit!r} to the Store",
            ),
            call(
                "trace",
                f"Commit workflow id: {fake_commit_workflow_id!r}",
            ),
            call(
                "progress",
                f"Committed {short_commit!r} to channel {'test/edge'!r}",
                permanent=True,
            ),
            call(
                "debug",
                f"Buildset id: {triggered_buildset_id!r}",
            ),
        ]
    )


def test_commit_does_not_allow_to_override_plane(
    source_store: SourceStoreService,
    fake_project: models.Project,
    fake_commit_sha: str,
    craft_publisher_gw_client_mock: MagicMock,
    fake_commit_workflow: CommitWorkflow,
    stored_plane: Plane,
    emitter: RecordingEmitter,
) -> None:
    project_name = fake_project.name
    fake_plane = Plane.from_str("user-defined/plane")
    with pytest.raises(
        IncorrectPlaneSpecifiedError,
        match=f"Incorrect plane '{fake_plane.name}' specified",
    ) as exc:
        source_store.commit(
            name=project_name,
            ref=fake_commit_sha,
            channel="test/edge",
            plane=fake_plane,
        )
    assert exc.value.details == (
        f"Provided plane differs from the stored value: '{fake_plane.name}'"
        f" (provided) != '{stored_plane.name}' (stored)"
    )
    craft_publisher_gw_client_mock.start_commit_workflow.assert_not_called()


@pytest.fixture
def fake_promote_workflow(craft_publisher_gw_client_mock: MagicMock) -> CommitWorkflow:
    created_at = datetime.now(timezone.utc)
    completed_at = created_at - timedelta(minutes=3, seconds=23)
    commit_workflow = get_commit_workflow(
        created_at=created_at,
        completed_at=completed_at,
        craft_channel=Channel(
            track="2.0-on-plane-24.04", risk="beta", name="2.0-on-plane-24.04/beta"
        ),
        commit_id="commit-workflow-id-213",
    )
    craft_publisher_gw_client_mock.get_commit_workflows.return_value = [commit_workflow]
    return commit_workflow


def test_promote_commit_non_interactive(
    source_store: SourceStoreService,
    craft_publisher_gw_client_mock: MagicMock,
    fake_promote_workflow: CommitWorkflow,
    emitter: RecordingEmitter,
) -> None:
    fake_commit_workflow_id = "commit-workflow-id-213"

    craft_publisher_gw_client_mock.start_promotion_workflow.return_value = (
        fake_commit_workflow_id
    )

    triggered_buildset_id = fake_promote_workflow.buildsets[0].entity_id

    source_store.promote_commit(
        name="starcraft-test",
        source_channel="2.0-on-plane-24.04/edge",
        plane=Plane.from_str("starcraft/test"),
    )

    craft_publisher_gw_client_mock.start_promotion_workflow.assert_called_with(
        package_name="starcraft-test",
        source_channel="2.0-on-plane-24.04/edge",
        plane=Plane.from_str("starcraft/test"),
    )

    emitter.assert_interactions(
        [
            call(
                "progress",
                "Triggering promotion of '2.0-on-plane-24.04/edge' to the Store",
            ),
            call(
                "trace",
                f"Commit workflow id: {fake_commit_workflow_id!r}",
            ),
            call(
                "progress",
                "Promoted '2.0-on-plane-24.04/edge' to '2.0-on-plane-24.04/beta'",
                permanent=True,
            ),
            call(
                "debug",
                f"Buildset id: {triggered_buildset_id!r}",
            ),
        ]
    )
