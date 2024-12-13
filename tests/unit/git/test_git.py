# Copyright 2023-2024 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License version 3 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


"""Tests for the pygit2 wrapper class."""

import re
import subprocess
from pathlib import Path
from typing import cast
from unittest.mock import ANY

import pygit2
import pygit2.enums
import pytest
import pytest_mock
import pytest_subprocess

from craft_application.git import (
    COMMIT_SHA_LEN,
    COMMIT_SHORT_SHA_LEN,
    CRAFTGIT_BINARY_NAME,
    GIT_FALLBACK_BINARY_NAME,
    NO_PUSH_URL,
    GitError,
    GitRepo,
    GitType,
    get_git_repo_type,
    is_commit,
    is_repo,
    is_short_commit,
    parse_describe,
    short_commit_sha,
)
from craft_application.remote import (
    RemoteBuildInvalidGitRepoError,
    check_git_repo_for_remote_build,
)
from tests.conftest import RepositoryDefinition


def test_is_repo(empty_working_directory):
    """Check if directory is a repo."""
    GitRepo(empty_working_directory)

    assert is_repo(empty_working_directory)


def test_is_not_repo(empty_working_directory):
    """Check if a directory is not a repo."""
    assert not is_repo(empty_working_directory)


def test_git_repo_type_invalid(empty_working_directory):
    """Check if directory is an invalid repo."""
    assert get_git_repo_type(empty_working_directory) == GitType.INVALID


def test_git_repo_type_normal(empty_working_directory):
    """Check if directory is a repo."""
    GitRepo(empty_working_directory)

    assert get_git_repo_type(empty_working_directory) == GitType.NORMAL


def test_git_repo_type_shallow(empty_working_directory):
    """Check if directory is a shallow cloned repo."""
    root_path = Path(empty_working_directory)
    git_normal_path = root_path / "normal"
    git_normal_path.mkdir()
    git_shallow_path = root_path / "shallow"

    repo_normal = GitRepo(git_normal_path)
    (repo_normal.path / "1").write_text("1")
    repo_normal.add_all()
    repo_normal.commit("1")

    (repo_normal.path / "2").write_text("2")
    repo_normal.add_all()
    repo_normal.commit("2")

    (repo_normal.path / "3").write_text("3")
    repo_normal.add_all()
    repo_normal.commit("3")

    # pygit2 does not support shallow cloning, so we use git directly
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            git_normal_path.absolute().as_uri(),
            git_shallow_path.absolute().as_posix(),
        ],
        check=True,
    )

    assert get_git_repo_type(git_shallow_path) == GitType.SHALLOW


@pytest.mark.usefixtures("empty_working_directory")
def test_is_repo_path_only():
    """Only look at the path for a repo."""
    Path("parent-repo/not-a-repo/child-repo").mkdir(parents=True)
    # create the parent and child repos
    GitRepo(Path("parent-repo"))
    GitRepo(Path("parent-repo/not-a-repo/child-repo"))

    assert is_repo(Path("parent-repo"))
    assert not is_repo(Path("parent-repo/not-a-repo"))
    assert is_repo(Path("parent-repo/not-a-repo/child-repo"))


def test_is_repo_error(empty_working_directory, mocker):
    """Raise an error if git fails to check a repo."""
    mocker.patch("pygit2.discover_repository", side_effect=pygit2.GitError)

    with pytest.raises(GitError) as raised:
        assert is_repo(empty_working_directory)

    assert raised.value.details == (
        f"Could not check for git repository in {str(empty_working_directory)!r}."
    )


@pytest.mark.parametrize(
    ("describe", "expected"),
    [
        ("cdaea14", "cdaea14"),
        ("4.1.1-0-gad012482d", "4.1.1"),
        ("4.1.1-16-g2d8943dbc", "4.1.1.post16+git2d8943dbc"),
        ("curl-8_11_0-6-g0cdde0f", "curl-8_11_0.post6+git0cdde0f"),
        ("curl-8_11_0-0-gb1ef0e1", "curl-8_11_0"),
        ("0ae7c04", "0ae7c04"),
        ("unknown-format", "unknown-format"),
    ],
)
def test_parsing_describe(describe: str, expected: str) -> None:
    """Check if describe result is correctly parsed."""
    assert parse_describe(describe) == expected


def test_init_repo(empty_working_directory):
    """Initialize a GitRepo object."""
    repo = GitRepo(empty_working_directory)

    assert is_repo(empty_working_directory)
    assert repo.path == empty_working_directory


def test_init_existing_repo(empty_working_directory):
    """Initialize a GitRepo object in an existing git repository."""
    # initialize a repo
    GitRepo(empty_working_directory)

    # creating a new GitRepo object will not re-initialize the repo
    repo = GitRepo(empty_working_directory)

    assert is_repo(empty_working_directory)
    assert repo.path == empty_working_directory


def test_init_repo_no_directory(empty_working_directory):
    """Raise an error if the directory is missing."""
    with pytest.raises(FileNotFoundError) as raised:
        GitRepo(empty_working_directory / "missing")

    assert str(raised.value) == (
        "Could not initialize a git repository because "
        f"{str(empty_working_directory / 'missing')!r} does not exist or is not a directory."
    )


def test_init_repo_not_a_directory(empty_working_directory):
    """Raise an error if the path is not a directory."""
    Path("regular-file").touch()

    with pytest.raises(FileNotFoundError) as raised:
        GitRepo(empty_working_directory / "regular-file")

    assert str(raised.value) == (
        "Could not initialize a git repository because "
        f"{str(empty_working_directory / 'regular-file')!r} does not exist or is not a directory."
    )


def test_init_repo_error(empty_working_directory, mocker):
    """Raise an error if the repo cannot be initialized."""
    mocker.patch("pygit2.init_repository", side_effect=pygit2.GitError)

    with pytest.raises(GitError) as raised:
        GitRepo(empty_working_directory)

    assert raised.value.details == (
        f"Could not initialize a git repository in {str(empty_working_directory)!r}."
    )


def test_add_all(empty_working_directory):
    """Add all files."""
    repo = GitRepo(empty_working_directory)
    (repo.path / "foo").touch()
    (repo.path / "bar").touch()
    repo.add_all()

    status = pygit2.Repository(empty_working_directory).status()

    if pygit2.__version__.startswith("1.13."):
        expected = {
            "foo": pygit2.GIT_STATUS_INDEX_NEW,  # pyright: ignore[reportAttributeAccessIssue]
            "bar": pygit2.GIT_STATUS_INDEX_NEW,  # pyright: ignore[reportAttributeAccessIssue]
        }
    else:
        expected = {
            "foo": pygit2.enums.FileStatus.INDEX_NEW,  # pyright: ignore[reportAttributeAccessIssue]
            "bar": pygit2.enums.FileStatus.INDEX_NEW,  # pyright: ignore[reportAttributeAccessIssue]
        }

    assert status == expected


def test_add_all_no_files_to_add(empty_working_directory):
    """`add_all` should succeed even if there are no files to add."""
    repo = GitRepo(empty_working_directory)
    repo.add_all()

    status = pygit2.Repository(empty_working_directory).status()

    assert status == {}


def test_add_all_error(empty_working_directory, mocker):
    """Raise an error if the changes could not be added."""
    mocker.patch("pygit2.Index.add_all", side_effect=pygit2.GitError)
    repo = GitRepo(empty_working_directory)

    with pytest.raises(GitError) as raised:
        repo.add_all()

    assert raised.value.details == (
        f"Could not add changes for the git repository in {str(empty_working_directory)!r}."
    )


def test_commit(empty_working_directory):
    """Commit a file and confirm it is in the tree."""
    repo = GitRepo(empty_working_directory)
    (repo.path / "test-file").touch()
    repo.add_all()

    repo.commit()

    # verify commit (the `isinstance` checks are to satisfy pyright)
    commit = pygit2.Repository(empty_working_directory).revparse_single("HEAD")
    assert isinstance(commit, pygit2.Commit)
    assert commit.message == "auto commit"
    assert commit.committer.name == "auto commit"
    assert commit.committer.email == "auto commit"

    # verify tree
    tree = commit.tree
    assert isinstance(tree, pygit2.Tree)
    assert len(tree) == 1

    # verify contents of tree
    blob = tree[0]
    assert isinstance(blob, pygit2.Blob)
    assert blob.name == "test-file"


def test_commit_write_tree_error(empty_working_directory, mocker):
    """Raise an error if the tree cannot be created."""
    mocker.patch("pygit2.Index.write_tree", side_effect=pygit2.GitError)
    repo = GitRepo(empty_working_directory)
    (repo.path / "test-file").touch()
    repo.add_all()

    with pytest.raises(GitError) as raised:
        repo.commit()

    assert raised.value.details == (
        f"Could not create a tree for the git repository in {str(empty_working_directory)!r}."
    )


def test_commit_error(empty_working_directory, mocker):
    """Raise an error if the commit cannot be created."""
    mocker.patch("pygit2.Repository.create_commit", side_effect=pygit2.GitError)
    repo = GitRepo(empty_working_directory)
    (repo.path / "test-file").touch()
    repo.add_all()

    with pytest.raises(GitError) as raised:
        repo.commit()

    assert raised.value.details == (
        f"Could not create a commit for the git repository in {str(empty_working_directory)!r}."
    )


def test_is_clean(empty_working_directory):
    """Check if a repo is clean."""
    repo = GitRepo(empty_working_directory)

    assert repo.is_clean()

    (repo.path / "foo").touch()

    assert not repo.is_clean()


def test_is_clean_error(empty_working_directory, mocker):
    """Check if git fails when checking if the repo is clean."""
    mocker.patch("pygit2.Repository.status", side_effect=pygit2.GitError)
    repo = GitRepo(empty_working_directory)

    with pytest.raises(GitError) as raised:
        repo.is_clean()

    assert raised.value.details == (
        f"Could not check if the git repository in {str(empty_working_directory)!r} is clean."
    )


@pytest.mark.usefixtures("empty_working_directory")
def test_push_url():
    """Push the default ref (HEAD) to a remote branch."""
    # create a local repo and make a commit
    Path("local-repo").mkdir()
    repo = GitRepo(Path("local-repo"))
    (repo.path / "test-file").touch()
    repo.add_all()
    repo.commit()
    # create a bare remote repo
    Path("remote-repo").mkdir()
    remote = pygit2.init_repository(Path("remote-repo"), bare=True)

    repo.push_url(
        remote_url=f"file://{str(Path('remote-repo').absolute())}",
        remote_branch="test-branch",
    )

    # verify commit in remote (the `isinstance` checks are to satisfy pyright)
    commit = remote.revparse_single("test-branch")
    assert isinstance(commit, pygit2.Commit)
    assert commit.message == "auto commit"
    assert commit.committer.name == "auto commit"
    assert commit.committer.email == "auto commit"
    # verify tree in remote
    tree = commit.tree
    assert isinstance(tree, pygit2.Tree)
    assert len(tree) == 1
    # verify contents of tree in remote
    blob = tree[0]
    assert isinstance(blob, pygit2.Blob)
    assert blob.name == "test-file"


@pytest.mark.usefixtures("empty_working_directory")
def test_push_url_raises_git_error_on_subprocess_error(mocker):
    """Push subprocess fails."""
    # create a local repo and make a commit
    Path("local-repo").mkdir()
    repo = GitRepo(Path("local-repo"))
    (repo.path / "test-file").touch()
    repo.add_all()
    repo.commit()

    mocked_subprocess = mocker.patch("subprocess.Popen")
    mocked_subprocess.side_effect = subprocess.SubprocessError

    with pytest.raises(GitError):
        repo.push_url(
            remote_url=f"file://{str(Path('remote-repo').absolute())}",
            remote_branch="test-branch",
        )


@pytest.mark.usefixtures("empty_working_directory")
def test_push_url_raises_git_error_on_subprocess_non_zero_exit(mocker):
    """Push subprocess fails."""
    # create a local repo and make a commit
    Path("local-repo").mkdir()
    repo = GitRepo(Path("local-repo"))
    (repo.path / "test-file").touch()
    repo.add_all()
    repo.commit()

    mocked_subprocess = mocker.patch("subprocess.Popen")
    mocked_subprocess.return_value.__enter__.return_value.returncode = 2
    with pytest.raises(GitError):
        repo.push_url(
            remote_url=f"file://{str(Path('remote-repo').absolute())}",
            remote_branch="test-branch",
        )


@pytest.mark.usefixtures("empty_working_directory")
def test_push_url_detached_head():
    """Push a detached HEAD to a remote branch."""
    # create a local repo and make two commits
    Path("local-repo").mkdir()
    repo = GitRepo(Path("local-repo"))
    (repo.path / "test-file-1").touch()
    repo.add_all()
    repo.commit()
    (repo.path / "test-file-2").touch()
    repo.add_all()
    repo.commit()
    # detach HEAD to first commit
    first_commit = repo._repo.revparse_single("HEAD~1")
    repo._repo.checkout_tree(first_commit)
    repo._repo.set_head(first_commit.id)
    # create a bare remote repo
    Path("remote-repo").mkdir()
    remote = pygit2.init_repository(Path("remote-repo"), bare=True)

    # push the detached HEAD to the remote
    repo.push_url(
        remote_url=f"file://{str(Path('remote-repo').absolute())}",
        remote_branch="test-branch",
    )

    # verify commit in remote (the `isinstance` checks are to satisfy pyright)
    commit = remote.revparse_single("test-branch")
    assert isinstance(commit, pygit2.Commit)
    assert commit.message == "auto commit"
    assert commit.committer.name == "auto commit"
    assert commit.committer.email == "auto commit"
    # verify tree in remote
    tree = commit.tree
    assert isinstance(tree, pygit2.Tree)
    assert len(tree) == 1
    # verify contents of tree in remote are from the first commit
    blob = tree[0]
    assert isinstance(blob, pygit2.Blob)
    assert blob.name == "test-file-1"


@pytest.mark.usefixtures("empty_working_directory")
def test_push_url_branch():
    """Push a branch to a remote branch."""
    # create a local repo and make a commit
    Path("local-repo").mkdir()
    repo = GitRepo(Path("local-repo"))
    (repo.path / "test-file").touch()
    repo.add_all()
    repo.commit()
    # create a bare remote repo
    Path("remote-repo").mkdir()
    remote = pygit2.init_repository(Path("remote-repo"), bare=True)

    repo.push_url(
        remote_url=f"file://{str(Path('remote-repo').absolute())}",
        remote_branch="test-branch",
        # use the branch name
        ref=repo._repo.head.shorthand,
    )

    # verify commit in remote (the `isinstance` checks are to satisfy pyright)
    commit = remote.revparse_single("test-branch")
    assert isinstance(commit, pygit2.Commit)
    assert commit.message == "auto commit"
    assert commit.committer.name == "auto commit"
    assert commit.committer.email == "auto commit"
    # verify tree in remote
    tree = commit.tree
    assert isinstance(tree, pygit2.Tree)
    assert len(tree) == 1
    # verify contents of tree in remote
    blob = tree[0]
    assert isinstance(blob, pygit2.Blob)
    assert blob.name == "test-file"


@pytest.mark.usefixtures("empty_working_directory")
def test_push_tags():
    """Verify that tags are push by trying to ref them from the remote."""
    # create a local repo and make a commit
    Path("local-repo").mkdir()
    repo = GitRepo(Path("local-repo"))
    (repo.path / "test-file").touch()
    repo.add_all()
    commit = repo.commit()
    tag = "tag1"
    repo._repo.create_reference(f"refs/tags/{tag}", commit)
    # create a bare remote repo
    Path("remote-repo").mkdir()
    remote = pygit2.init_repository(Path("remote-repo"), bare=True)

    repo.push_url(
        remote_url=f"file://{str(Path('remote-repo').absolute())}",
        remote_branch="test-branch",
        push_tags=True,
    )

    # verify commit through tag in remote (the `isinstance` checks are to satisfy pyright)
    commit = remote.revparse_single(tag)
    assert isinstance(commit, pygit2.Commit)
    assert commit.message == "auto commit"
    assert commit.committer.name == "auto commit"
    assert commit.committer.email == "auto commit"
    # verify tree in remote
    tree = commit.tree
    assert isinstance(tree, pygit2.Tree)
    assert len(tree) == 1
    # verify contents of tree in remote
    blob = tree[0]
    assert isinstance(blob, pygit2.Blob)
    assert blob.name == "test-file"


def test_push_url_refspec_unknown_ref(empty_working_directory):
    """Raise an error for an unknown refspec."""
    repo = GitRepo(empty_working_directory)

    with pytest.raises(GitError) as raised:
        repo.push_url(remote_url="test-url", remote_branch="test-branch", ref="bad-ref")

    assert raised.value.details == (
        "Could not resolve reference 'bad-ref' for the git repository "
        f"in {str(empty_working_directory)!r}."
    )


@pytest.mark.parametrize(
    ("url", "expected_url"),
    [
        # no-op if token is not in url
        ("fake-url", "fake-url"),
        # hide single occurrence of the token
        ("fake-url/test-token", "fake-url/<token>"),
        # hide multiple occurrences of the token
        ("fake-url/test-token/test-token", "fake-url/<token>/<token>"),
    ],
)
def test_push_url_hide_token(url, expected_url, mocker, empty_working_directory):
    """Hide the token in the log and error output."""
    mock_logs = mocker.patch("logging.Logger.debug")

    repo = GitRepo(empty_working_directory)
    (repo.path / "test-file").touch()
    repo.add_all()
    repo.commit()
    expected_error_details = (
        f"Could not push 'HEAD' to {expected_url!r} with refspec "
        "'.*:refs/heads/test-branch' for the git repository "
        f"in {str(empty_working_directory)!r}."
    )

    with pytest.raises(GitError) as raised:
        repo.push_url(
            remote_url=url,
            remote_branch="test-branch",
            token="test-token",
        )

    # token should be hidden in the log output
    mock_logs.assert_called_with(
        # The last argument is the refspec `.*:refs/heads/test-branch`, which can only
        # be asserted with regex. It is not relevant to this test, so `ANY` is used.
        "Pushing %r to remote %r with refspec %r.",
        "HEAD",
        expected_url,
        ANY,
    )

    # token should be hidden in the error message
    assert raised.value.details is not None
    assert re.match(expected_error_details, raised.value.details)


def test_push_url_refspec_git_error(mocker, empty_working_directory):
    """Raise an error if git fails when looking for a refspec."""
    mocker.patch(
        "pygit2.Repository.lookup_reference_dwim",
        side_effect=pygit2.GitError,
    )
    repo = GitRepo(empty_working_directory)

    with pytest.raises(GitError) as raised:
        repo.push_url(remote_url="test-url", remote_branch="test-branch", ref="bad-ref")

    assert raised.value.details == (
        "Could not resolve reference 'bad-ref' for the git repository "
        f"in {str(empty_working_directory)!r}."
    )


def test_push_url_push_error(empty_working_directory):
    """Raise an error when the refspec cannot be pushed."""
    repo = GitRepo(empty_working_directory)
    (repo.path / "test-file").touch()
    repo.add_all()
    repo.commit()
    expected_error_details = (
        "Could not push 'HEAD' to 'bad-url' with refspec "
        "'.*:refs/heads/test-branch' for the git repository "
        f"in {str(empty_working_directory)!r}."
    )

    with pytest.raises(GitError) as raised:
        repo.push_url(remote_url="bad-url", remote_branch="test-branch")

    assert raised.value.details is not None
    assert re.match(expected_error_details, raised.value.details)


def test_check_git_repo_for_remote_build_invalid(empty_working_directory):
    """Check if directory is an invalid repo."""
    with pytest.raises(
        RemoteBuildInvalidGitRepoError, match="Could not find a git repository in"
    ):
        check_git_repo_for_remote_build(empty_working_directory)


@pytest.fixture
def patched_cloning_process(mocker):
    return mocker.patch(
        "craft_parts.utils.os_utils.process_run",
    )


def test_clone_repository_wraps_called_process_error(
    patched_cloning_process, empty_working_directory
):
    """Test if error is raised if clone failed."""
    patched_cloning_process.side_effect = subprocess.CalledProcessError(
        returncode=1, cmd="git clone"
    )
    fake_repo_url = "fake-repository-url.localhost"
    with pytest.raises(GitError) as raised:
        GitRepo.clone_repository(url=fake_repo_url, path=empty_working_directory)
    assert raised.value.details == (
        f"cannot clone repository: {fake_repo_url} "
        f"to {str(empty_working_directory)!r}"
    )


def test_clone_repository_wraps_file_not_found_error(
    patched_cloning_process, empty_working_directory
):
    """Test if error is raised if git is not found."""
    patched_cloning_process.side_effect = FileNotFoundError
    fake_repo_url = "fake-repository-url.localhost"
    fake_branch = "some-fake-branch"
    with pytest.raises(GitError) as raised:
        GitRepo.clone_repository(
            url=fake_repo_url,
            path=empty_working_directory,
            checkout_branch=fake_branch,
        )
    assert raised.value.details == "git command not found in the system"


@pytest.mark.parametrize(
    ("kwargs", "expected_cmd_args"),
    [
        (
            {"checkout_branch": "feat/new-glowing-feature"},
            ["--branch", "feat/new-glowing-feature"],
        ),
        (
            {"checkout_branch": "feat/new-glowing-feature", "single_branch": True},
            ["--branch", "feat/new-glowing-feature", "--single-branch"],
        ),
        (
            {"single_branch": True},
            ["--single-branch"],
        ),
        (
            {"depth": 1},
            ["--depth", "1"],
        ),
        (
            {"depth": 0},
            [],
        ),
        (
            {},
            [],
        ),
    ],
)
def test_clone_repository_appends_correct_parameters_to_clone_command(
    mocker, empty_repository, kwargs, expected_cmd_args, patched_cloning_process
) -> None:
    """Test if GitRepo uses correct arguments in subprocess calls."""
    # it is not a repo before clone is triggered, but will be after fake pygit2.clone_repository is called
    mocker.patch("craft_application.git._git_repo.is_repo", side_effect=[False, True])
    mocked_init = mocker.patch.object(GitRepo, "_init_repo")
    fake_repo_url = "fake-repository-url.localhost"
    from craft_application.git._git_repo import logger as git_repo_logger

    _ = GitRepo.clone_repository(
        url=fake_repo_url,
        path=empty_repository,
        **kwargs,
    )
    mocked_init.assert_not_called()
    patched_cloning_process.assert_called_with(
        [
            "git",
            "clone",
            *expected_cmd_args,
            fake_repo_url,
            str(empty_repository),
        ],
        git_repo_logger.debug,
    )


@pytest.mark.usefixtures("patched_cloning_process")
def test_clone_repository_returns_git_repo_on_succcess_clone(mocker, empty_repository):
    """Test if GitRepo is return on clone success."""
    # it is not a repo before clone is triggered, but will be after fake pygit2.clone_repository is called
    mocker.patch("craft_application.git._git_repo.is_repo", side_effect=[False, True])
    mocked_init = mocker.patch.object(GitRepo, "_init_repo")
    fake_repo_url = "fake-repository-url.localhost"
    fake_branch = "some-fake-branch"

    repo = GitRepo.clone_repository(
        url=fake_repo_url,
        path=empty_repository,
        checkout_branch=fake_branch,
    )
    mocked_init.assert_not_called()
    assert isinstance(repo, GitRepo)


def test_clone_repository_raises_in_existing_repo(mocker, empty_working_directory):
    """Test if error is raised on clone to already existing repository."""
    # it is not a repo before clone is triggered, but will be after fake pygit2.clone_repository is called
    mocker.patch("craft_application.git._git_repo.is_repo", return_value=True)

    with pytest.raises(GitError) as exc:
        GitRepo.clone_repository(url="some-url.localhost", path=empty_working_directory)

    assert exc.value.details == "Cannot clone to existing repository"


def test_check_git_repo_for_remote_build_normal(empty_working_directory):
    """Check if directory is a repo."""
    GitRepo(empty_working_directory)
    check_git_repo_for_remote_build(empty_working_directory)


def test_check_git_repo_remote_exists(mocker, empty_working_directory):
    """Check if True is returned if remote exists."""
    repo = GitRepo(empty_working_directory)
    remote_name = "existing-remote"
    mocked_remotes = mocker.patch.object(repo._repo, "remotes")
    mocked_remotes.__getitem__.return_value = "test"

    assert repo.remote_exists(remote_name) is True, f"Remote {remote_name} should exist"
    mocked_remotes.__getitem__.assert_called_with(remote_name)


def test_check_git_repo_remote_not_exists(mocker, empty_working_directory):
    """Check if False is returned if remote does not exist."""
    repo = GitRepo(empty_working_directory)
    non_existing_remote = "non-existing-remote"
    mocked_remotes = mocker.patch.object(repo._repo, "remotes")
    mocked_remotes.__getitem__.side_effect = KeyError

    assert (
        repo.remote_exists(non_existing_remote) is False
    ), f"Remote {non_existing_remote} should not exist"
    mocked_remotes.__getitem__.assert_called_with(non_existing_remote)


def test_check_git_repo_add_remote(mocker, empty_working_directory):
    """Check if add_remote is called correctly."""
    repo = GitRepo(empty_working_directory)
    new_remote_name = "new-remote"
    mocked_fn = mocker.patch.object(repo._repo.remotes, "create")
    repo.add_remote(new_remote_name, "https://git.fake-remote-url.localhost")
    mocked_fn.assert_called_with(
        new_remote_name, "https://git.fake-remote-url.localhost"
    )


def test_check_git_repo_add_remote_value_error_is_wrapped(
    mocker, empty_working_directory
):
    """Check if ValueError is wrapped correctly when adding same remote twice."""
    repo = GitRepo(empty_working_directory)
    new_remote_name = "new-remote"
    mocker.patch.object(repo._repo.remotes, "create", side_effect=[True, ValueError])
    repo.add_remote(new_remote_name, "https://git.fake-remote-url.localhost")

    with pytest.raises(GitError) as ge:
        repo.add_remote(new_remote_name, "https://git.fake-remote-url.localhost")
    assert ge.value.details == f"remote '{new_remote_name}' already exists."


def test_check_git_repo_add_remote_pygit_error_is_wrapped(
    mocker, empty_working_directory
):
    """Check if ValueError is wrapped correctly when adding same remote twice."""
    repo = GitRepo(empty_working_directory)
    new_remote_name = "new-remote"
    mocker.patch.object(repo._repo.remotes, "create", side_effect=pygit2.GitError)

    with pytest.raises(GitError) as ge:
        repo.add_remote(new_remote_name, "https://git.fake-remote-url.localhost")
    expected_err_msg = (
        "could not add remote to a git "
        f"repository in {str(empty_working_directory)!r}."
    )
    assert ge.value.details == expected_err_msg


def test_check_git_repo_rename_remote(mocker, empty_working_directory):
    """Check if rename_remote is called correctly."""
    repo = GitRepo(empty_working_directory)
    remote_name = "remote"
    new_remote_name = "new-remote"
    mocked_fn = mocker.patch.object(repo._repo.remotes, "rename")
    repo.rename_remote(remote_name, new_remote_name)
    mocked_fn.assert_called_with(remote_name, new_remote_name)


def test_check_git_repo_rename_remote_key_error_is_wrapped(
    mocker, empty_working_directory
):
    """Check if KeyError is wrapped correctly when renaming non-existing remote."""
    repo = GitRepo(empty_working_directory)
    remote_name = "non-existing-remote"
    new_remote_name = "new-remote"
    mocker.patch.object(repo._repo.remotes, "rename", side_effect=KeyError)
    with pytest.raises(GitError) as ge:
        repo.rename_remote(remote_name, new_remote_name)
    assert ge.value.details == f"remote '{remote_name}' does not exist."


def test_check_git_repo_rename_remote_value_error_is_wrapped(
    mocker, empty_working_directory
):
    """Check if ValueError is wrapped correctly when new name is incorrect."""
    repo = GitRepo(empty_working_directory)
    remote_name = "remote"
    new_remote_name = "wrong-@$!~@-remote"
    mocker.patch.object(repo._repo.remotes, "rename", side_effect=ValueError)
    with pytest.raises(GitError) as ge:
        repo.rename_remote(remote_name, new_remote_name)
    assert (
        ge.value.details == f"wrong name '{new_remote_name}' for the remote provided."
    )


def test_check_git_repo_rename_remote_pygit_error_is_wrapped(
    mocker, empty_working_directory
):
    """Check if ValueError is wrapped correctly when adding same remote twice."""
    repo = GitRepo(empty_working_directory)
    remote_name = "remote"
    new_remote_name = "new-remote"
    mocker.patch.object(repo._repo.remotes, "rename", side_effect=pygit2.GitError)

    with pytest.raises(GitError) as ge:
        repo.rename_remote(remote_name, new_remote_name)
    expected_err_msg = f"cannot rename '{remote_name}' to '{new_remote_name}'"
    assert ge.value.details == expected_err_msg


class _FakeRemote:
    def __init__(
        self,
        fake_remote_url: str,
        fake_remote_push_url: str | None = None,
    ) -> None:
        self._fake_remote_url = fake_remote_url
        self._fake_remote_push_url = fake_remote_push_url

    @property
    def url(self) -> str:
        return self._fake_remote_url

    @property
    def push_url(self) -> str | None:
        return self._fake_remote_push_url

    def set_url(self, new_url: str) -> None:
        self._fake_remote_url = new_url

    def set_push_url(self, new_push_url: str) -> None:
        self._fake_remote_push_url = new_push_url


def test_git_repo_get_remote_url(mocker, empty_working_directory):
    repo = GitRepo(empty_working_directory)
    test_fake_existing_remote = "test-remote"
    fake_remote_url = "https://test-remote-url.localhost"

    mocked_remotes = mocker.patch.object(repo._repo, "remotes")
    mocked_remotes.__getitem__ = lambda _s, _i: _FakeRemote(fake_remote_url)

    assert repo.get_remote_url(test_fake_existing_remote) == fake_remote_url


def test_git_repo_get_remote_push_url_default(mocker, empty_working_directory):
    repo = GitRepo(empty_working_directory)
    test_fake_existing_remote = "test-remote"
    fake_remote_url = "https://test-remote-url.localhost"

    mocked_remotes = mocker.patch.object(repo._repo, "remotes")
    mocked_remotes.__getitem__ = lambda _s, _i: _FakeRemote(fake_remote_url)

    assert repo.get_remote_push_url(test_fake_existing_remote) is None


def test_check_git_repo_get_remote_push_url_if_set(mocker, empty_working_directory):
    repo = GitRepo(empty_working_directory)
    test_fake_existing_remote = "test-remote"
    fake_remote_url = "https://test-remote-url.localhost"

    mocked_remotes = mocker.patch.object(repo._repo, "remotes")
    fake_remote = _FakeRemote(fake_remote_url)
    custom_push_url = "https://custom-push-url.localhost"
    fake_remote.set_push_url(custom_push_url)

    mocked_remotes.__getitem__ = lambda _s, _i: fake_remote

    assert repo.get_remote_push_url(test_fake_existing_remote) == custom_push_url


def test_git_repo_get_remote_push_url_fails_if_remote_does_not_exist(
    mocker, empty_working_directory
):
    """Check if GitError is raised if remote does not exist."""
    repo = GitRepo(empty_working_directory)
    test_fake_existing_remote = "test-remote"
    mocked_remotes = mocker.patch.object(repo._repo, "remotes")
    mocked_remotes.__getitem__.side_effect = KeyError

    with pytest.raises(GitError):
        repo.get_remote_push_url(test_fake_existing_remote)


def test_git_repo_get_remote_url_fails_if_remote_does_not_exist(
    mocker, empty_working_directory
):
    """Check if GitError is raised if remote does not exist."""
    repo = GitRepo(empty_working_directory)
    test_fake_existing_remote = "test-remote"
    mocked_remotes = mocker.patch.object(repo._repo, "remotes")
    mocked_remotes.__getitem__.side_effect = KeyError

    with pytest.raises(GitError):
        repo.get_remote_url(test_fake_existing_remote)


def test_git_repo_set_remote_url(mocker, empty_working_directory):
    repo = GitRepo(empty_working_directory)
    test_remote = "test-remote"
    updated_remote_url = "https://new-remote-url.localhost"

    mocked_remotes = mocker.patch.object(repo._repo, "remotes")
    repo.set_remote_url(test_remote, updated_remote_url)

    mocked_remotes.set_url.assert_called_with(test_remote, updated_remote_url)


def test_git_repo_set_remote_url_non_existing_remote(empty_repository: Path):
    repo = GitRepo(empty_repository)
    non_existing_remote = "non-existing-remote"
    updated_remote_url = "https://new-remote-url.localhost"

    with pytest.raises(GitError) as git_error:
        repo.set_remote_url(non_existing_remote, updated_remote_url)

    assert (
        git_error.value.details
        == f"cannot set URL for non-existing remote: {non_existing_remote!r}"
    )


def test_git_repo_set_remote_push_url(mocker, empty_working_directory):
    repo = GitRepo(empty_working_directory)
    test_remote = "test-remote"
    updated_remote_url = "https://new-remote-push-url.localhost"

    mocked_remotes = mocker.patch.object(repo._repo, "remotes")
    repo.set_remote_push_url(test_remote, updated_remote_url)

    mocked_remotes.set_push_url.assert_called_with(test_remote, updated_remote_url)


def test_git_repo_set_remote_push_url_non_existing_remote(empty_repository: Path):
    repo = GitRepo(empty_repository)
    non_existing_remote = "non-existing-remote"
    updated_remote_url = "https://new-remote-push-url.localhost"

    with pytest.raises(GitError) as git_error:
        repo.set_remote_push_url(non_existing_remote, updated_remote_url)

    assert (
        git_error.value.details
        == f"cannot set push URL for non-existing remote: {non_existing_remote!r}"
    )


def test_check_git_repo_set_no_push(mocker, empty_working_directory):
    """Check if url is returned correctly using the get_url API."""
    repo = GitRepo(empty_working_directory)
    test_remote = "test-remote"

    mocked_remotes = mocker.patch.object(repo._repo, "remotes")
    repo.set_no_push(test_remote)

    mocked_remotes.set_push_url.assert_called_with(test_remote, NO_PUSH_URL)


def test_check_git_repo_for_remote_build_shallow(empty_working_directory):
    """Check if directory is a shallow cloned repo."""
    root_path = Path(empty_working_directory)
    git_normal_path = root_path / "normal"
    git_normal_path.mkdir()
    git_shallow_path = root_path / "shallow"

    repo_normal = GitRepo(git_normal_path)
    (repo_normal.path / "1").write_text("1")
    repo_normal.add_all()
    repo_normal.commit("1")

    (repo_normal.path / "2").write_text("2")
    repo_normal.add_all()
    repo_normal.commit("2")

    (repo_normal.path / "3").write_text("3")
    repo_normal.add_all()
    repo_normal.commit("3")

    # pygit2 does not support shallow cloning, so we use git directly
    subprocess.run(
        [
            "git",
            "clone",
            "--depth",
            "1",
            git_normal_path.absolute().as_uri(),
            git_shallow_path.absolute().as_posix(),
        ],
        check=True,
    )

    with pytest.raises(
        RemoteBuildInvalidGitRepoError,
        match="Remote builds for shallow cloned git repos are not supported",
    ):
        check_git_repo_for_remote_build(git_shallow_path)


def test_retriving_last_commit(empty_repository: Path) -> None:
    git_repo = GitRepo(empty_repository)
    (git_repo.path / "1").write_text("1")
    git_repo.add_all()
    test_commit_message = "test: add commit message"
    git_repo.commit(test_commit_message)
    commit = git_repo.get_last_commit()
    assert commit is not None, "Commit should be created and retrieved"
    assert len(commit.sha) == COMMIT_SHA_LEN, "Commit hash should have full length"
    assert is_commit(commit.sha), "Returned value should be a valid commit"
    assert (
        commit.sha[:COMMIT_SHORT_SHA_LEN] == commit.short_sha
    ), "Commit should have proper short version"


def test_last_commit_on_empty_repository(empty_repository: Path) -> None:
    """Test if last_commit errors out with correct error."""
    git_repo = GitRepo(empty_repository)
    with pytest.raises(GitError) as git_error:
        git_repo.get_last_commit()
    assert git_error.value.details == "could not retrieve last commit"


@pytest.mark.parametrize(
    "tags", [True, False], ids=lambda x: "tags" if x else "no_tags"
)
@pytest.mark.parametrize(
    "depth", [None, 1], ids=lambda x: "with_{x}_depth" if x else "no_depth"
)
@pytest.mark.parametrize(
    "ref", [None, "aaaaaaa"], ids=lambda x: f"with_ref_{x}" if x else "no_ref_specified"
)
def test_fetching_remote(
    empty_repository: Path,
    fake_process: pytest_subprocess.FakeProcess,
    expected_git_command: str,
    depth: int | None,
    ref: str | None,
    *,
    tags: bool,
) -> None:
    git_repo = GitRepo(empty_repository)
    remote = "test-remote"
    git_repo.add_remote(remote, "https://non-existing-repo.localhost")
    cmd = [expected_git_command, "fetch"]
    if tags:
        cmd.append("--tags")
    if depth is not None:
        cmd.extend(["--depth", str(depth)])
    cmd.append(remote)
    if ref is not None:
        cmd.append(ref)
    fake_process.register(cmd)
    git_repo.fetch(remote=remote, tags=tags, depth=depth, ref=ref)


def test_fetching_remote_fails(
    empty_repository: Path,
    fake_process: pytest_subprocess.FakeProcess,
    expected_git_command: str,
) -> None:
    git_repo = GitRepo(empty_repository)
    remote = "test-remote"
    git_repo.add_remote(remote, "https://non-existing-repo.localhost")
    cmd = [expected_git_command, "fetch"]
    cmd.append(remote)
    fake_process.register(cmd, returncode=1)
    with pytest.raises(GitError) as git_error:
        git_repo.fetch(remote=remote)
    assert git_error.value.details == f"cannot fetch remote: {remote!r}"


def test_fetching_fails_if_git_not_available(
    empty_repository: Path,
    mocker: pytest_mock.MockerFixture,
) -> None:
    git_repo = GitRepo(empty_repository)
    remote = "test-remote"
    git_repo.add_remote(remote, "https://non-existing-repo.localhost")
    patched_process_run = mocker.patch("craft_parts.utils.os_utils.process_run")
    patched_process_run.side_effect = FileNotFoundError
    with pytest.raises(GitError) as git_error:
        git_repo.fetch(remote=remote)
    assert git_error.value.details == "git command not found in the system"


def test_fetching_undefined_remote(empty_repository: Path) -> None:
    git_repo = GitRepo(empty_repository)
    remote = "test-non-existing-remote"
    with pytest.raises(GitError) as git_error:
        git_repo.fetch(remote=remote)
    assert git_error.value.details == f"cannot fetch undefined remote: {remote!r}"


@pytest.mark.parametrize(
    ("commit_str", "is_valid"),
    [
        ("test", False),
        ("fake-commit", False),
        ("1234", False),
        ("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", False),
        ("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", True),
        ("9d51ca832224e9a31e1898dd11b2764374402f09", True),
        ("9d51ca832224e9a31e1898dd11b2764374402f09a", False),
        ("9d51ca8", False),
        ("aaaaaaa", False),
    ],
)
def test_is_commit(commit_str: str, *, is_valid: bool) -> None:
    """Check function that checks if something is a valid sha."""
    assert is_commit(commit_str) is is_valid


@pytest.mark.parametrize(
    ("commit_str", "is_valid"),
    [
        ("test", False),
        ("fake-commit", False),
        ("1234", False),
        ("xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx", False),
        ("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa", False),
        ("9d51ca832224e9a31e1898dd11b2764374402f09", False),
        ("9d51ca832224e9a31e1898dd11b2764374402f09a", False),
        ("9d51ca8", True),
        ("aaaaaaa", True),
    ],
)
def test_is_short_commit(commit_str: str, *, is_valid: bool) -> None:
    """Check function that checks if something is a valid sha."""
    assert is_short_commit(commit_str) is is_valid


@pytest.mark.parametrize(
    ("remote", "command_output", "response"),
    [
        ("some-remote", "some-remote-postfix/branch", False),
        ("some-remote", "some-remote/main", True),
        ("some-remote", "other-remote/main", False),
        ("some-remote", "", False),
    ],
)
def test_remote_contains(
    empty_repository: Path,
    fake_process: pytest_subprocess.FakeProcess,
    remote: str,
    command_output: str,
    expected_git_command: str,
    *,
    response: bool,
) -> None:
    fake_process.register(
        [expected_git_command, "branch", "--remotes", "--contains", "fake-commit-sha"],
        stdout=command_output,
    )
    git_repo = GitRepo(empty_repository)
    assert (
        git_repo.remote_contains(remote=remote, commit_sha="fake-commit-sha")
        is response
    )


def test_remote_contains_fails_if_subprocess_fails(
    empty_repository: Path,
    fake_process: pytest_subprocess.FakeProcess,
    expected_git_command: str,
) -> None:
    fake_process.register(
        [expected_git_command, "branch", "--remotes", "--contains", "fake-commit-sha"],
        returncode=1,
    )
    git_repo = GitRepo(empty_repository)
    with pytest.raises(GitError) as git_error:
        git_repo.remote_contains(remote="fake-remote", commit_sha="fake-commit-sha")
    assert git_error.value.details == "incorrect commit provided, cannot check"


@pytest.mark.parametrize(
    "always_use_long_format",
    [True, False, None],
    ids=lambda p: f"use_long_format={p!s}",
)
def test_describing_commit(
    repository_with_commit: RepositoryDefinition, always_use_long_format: bool | None
):
    """Describe an empty repository."""
    repo = GitRepo(repository_with_commit.repository_path)

    assert (
        repo.describe(
            show_commit_oid_as_fallback=True,
            always_use_long_format=always_use_long_format,
        )
        == repository_with_commit.short_commit
    )


def test_describing_repo_fails_in_empty_repo(empty_repository: Path):
    """Cannot describe an empty repository."""
    repo = GitRepo(empty_repository)

    with pytest.raises(GitError):
        repo.describe(show_commit_oid_as_fallback=True)


def test_describing_tags(repository_with_annotated_tag: RepositoryDefinition):
    """Describe should be able to handle annotated tags."""
    repo = GitRepo(repository_with_annotated_tag.repository_path)
    assert repo.describe() == repository_with_annotated_tag.tag


@pytest.fixture(params=[True, False, None], ids=lambda p: f"fallback={p!r}")
def show_commit_oid_as_fallback(request: pytest.FixtureRequest) -> bool | None:
    return cast(bool | None, request.param)


@pytest.fixture(params=[True, False, None], ids=lambda p: f"long={p!r}")
def always_use_long_format(request: pytest.FixtureRequest) -> bool | None:
    return cast(bool | None, request.param)


def test_describing_commits_following_tags(
    repository_with_annotated_tag: RepositoryDefinition,
    show_commit_oid_as_fallback: bool | None,
    always_use_long_format: bool | None,
):
    """Describe should be able to discover commits after tags."""
    repo = GitRepo(repository_with_annotated_tag.repository_path)
    (repository_with_annotated_tag.repository_path / "another_file").touch()
    tag = repository_with_annotated_tag.tag
    repo.add_all()
    new_commit = repo.commit("commit after tag")
    short_new_commit = short_commit_sha(new_commit)
    describe_result = repo.describe(
        show_commit_oid_as_fallback=show_commit_oid_as_fallback,
        always_use_long_format=always_use_long_format,
    )
    assert describe_result == f"{tag}-1-g{short_new_commit}"
    assert parse_describe(describe_result) == f"{tag}.post1+git{short_new_commit}"


def test_describing_unanotated_tags(
    repository_with_unannotated_tag: RepositoryDefinition,
):
    """Describe should error out if trying to describe repo without annotated tags."""
    repo = GitRepo(repository_with_unannotated_tag.repository_path)
    with pytest.raises(GitError):
        repo.describe()


def test_describing_fallback_to_commit_for_unannotated_tags(
    repository_with_unannotated_tag: RepositoryDefinition,
):
    """Describe should fallback to commit if trying to describe repo without annotated tags."""
    repo = GitRepo(repository_with_unannotated_tag.repository_path)
    describe_result = repo.describe(show_commit_oid_as_fallback=True)
    assert describe_result == repository_with_unannotated_tag.short_commit


@pytest.mark.usefixtures("clear_git_binary_name_cache")
@pytest.mark.parametrize(
    ("craftgit_exists"),
    [
        pytest.param(True, id="craftgit_available"),
        pytest.param(False, id="fallback_to_git"),
    ],
)
def test_craftgit_is_used_for_git_operations(
    mocker: pytest_mock.MockerFixture,
    *,
    craftgit_exists: bool,
) -> None:
    which_res = f"/some/path/to/{CRAFTGIT_BINARY_NAME}" if craftgit_exists else None
    which_mock = mocker.patch("shutil.which", return_value=which_res)

    expected_binary = (
        CRAFTGIT_BINARY_NAME if craftgit_exists else GIT_FALLBACK_BINARY_NAME
    )
    assert GitRepo.get_git_command() == expected_binary

    which_mock.assert_called_once_with(CRAFTGIT_BINARY_NAME)


@pytest.mark.usefixtures("clear_git_binary_name_cache")
@pytest.mark.parametrize(
    ("craftgit_exists"),
    [
        pytest.param(True, id="craftgit_available"),
        pytest.param(False, id="fallback_to_git"),
    ],
)
def test_get_git_command_result_is_cached(
    mocker: pytest_mock.MockerFixture,
    *,
    craftgit_exists: bool,
) -> None:
    which_res = f"/some/path/to/{CRAFTGIT_BINARY_NAME}" if craftgit_exists else None
    which_mock = mocker.patch("shutil.which", return_value=which_res)

    expected_binary = (
        CRAFTGIT_BINARY_NAME if craftgit_exists else GIT_FALLBACK_BINARY_NAME
    )
    for _ in range(3):
        assert GitRepo.get_git_command() == expected_binary

    which_mock.assert_called_once_with(CRAFTGIT_BINARY_NAME)


def test_last_commit_on_branch_or_tag_fails_if_commit_not_found(
    empty_repository: Path,
    fake_process: pytest_subprocess.FakeProcess,
    expected_git_command: str,
) -> None:
    git_repo = GitRepo(empty_repository)
    branch_or_tag = "test"
    commit = "non-existent-commit"
    fake_process.register(
        [expected_git_command, "rev-list", "-n", "1", branch_or_tag],
        stdout=commit,
    )
    with pytest.raises(GitError) as git_error:
        git_repo.get_last_commit_on_branch_or_tag(branch_or_tag)
    assert (
        git_error.value.details == f"cannot find commit: {short_commit_sha(commit)!r}"
    )


def test_last_commit_on_branch_or_tag_fails_if_ref_not_found(
    empty_repository: Path,
    fake_process: pytest_subprocess.FakeProcess,
    expected_git_command: str,
) -> None:
    git_repo = GitRepo(empty_repository)
    branch_or_tag = "test"
    fake_process.register(
        [expected_git_command, "rev-list", "-n", "1", branch_or_tag],
        returncode=1,
        stderr=f"fatal: ambiguous argument {branch_or_tag!r}",
    )
    with pytest.raises(GitError) as git_error:
        git_repo.get_last_commit_on_branch_or_tag(branch_or_tag)
    err_details = cast(str, git_error.value.details)
    assert err_details.startswith(f"cannot find ref: {branch_or_tag!r}")
    assert "fatal" in err_details


def test_get_last_commit_on_branch_or_tag(
    repository_with_commit: RepositoryDefinition,
    fake_process: pytest_subprocess.FakeProcess,
    expected_git_command: str,
) -> None:
    git_repo = GitRepo(repository_with_commit.repository_path)
    branch_or_tag = "test"
    last_commit = git_repo.get_last_commit()
    fake_process.register(
        [expected_git_command, "rev-list", "-n", "1", branch_or_tag],
        stdout=last_commit.sha,
    )
    last_commit_on_branch = git_repo.get_last_commit_on_branch_or_tag(branch_or_tag)
    assert last_commit_on_branch == last_commit


@pytest.mark.parametrize("fetch", [True, False])
def test_last_commit_on_branch_with_fetching_remote(
    repository_with_commit: RepositoryDefinition,
    fake_process: pytest_subprocess.FakeProcess,
    expected_git_command: str,
    mocker: pytest_mock.MockerFixture,
    *,
    fetch: bool,
) -> None:
    git_repo = GitRepo(repository_with_commit.repository_path)
    fetch_mock = mocker.patch.object(git_repo, "fetch")
    test_remote = "remote-repo"

    branch_or_tag = "test"
    last_commit = git_repo.get_last_commit()
    fake_process.register(
        [expected_git_command, "rev-list", "-n", "1", branch_or_tag],
        stdout=last_commit.sha,
    )

    git_repo.get_last_commit_on_branch_or_tag(
        branch_or_tag, remote=test_remote, fetch=fetch
    )
    if fetch:
        fetch_mock.assert_called_with(remote=test_remote, tags=True)
    else:
        fetch_mock.assert_not_called()
