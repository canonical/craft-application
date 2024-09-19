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

import os
import pathlib
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path
from typing import cast
from unittest.mock import ANY

import pygit2
import pygit2.enums
import pytest
from craft_application.git import GitError, GitRepo, GitType, get_git_repo_type, is_repo
from craft_application.remote import (
    RemoteBuildInvalidGitRepoError,
    check_git_repo_for_remote_build,
)


@pytest.fixture
def empty_working_directory(tmp_path) -> Iterator[Path]:
    cwd = pathlib.Path.cwd()

    repo_dir = Path(tmp_path, "test-repo")
    repo_dir.mkdir()
    os.chdir(repo_dir)
    yield repo_dir

    os.chdir(cwd)


@pytest.fixture
def empty_repository(empty_working_directory) -> Path:
    subprocess.run(["git", "init"], check=True)
    return cast(Path, empty_working_directory)


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
            token="test-token",  # noqa: S106
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
    fake_repo_url = "fake-repository-url.local"
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
    fake_repo_url = "fake-repository-url.local"
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
    fake_repo_url = "fake-repository-url.local"
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
    fake_repo_url = "fake-repository-url.local"
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
        GitRepo.clone_repository(url="some-url.local", path=empty_working_directory)

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
    repo.add_remote(new_remote_name, "https://git.fake-remote-url.local")
    mocked_fn.assert_called_with(new_remote_name, "https://git.fake-remote-url.local")


def test_check_git_repo_add_remote_value_error_is_wrapped(
    mocker, empty_working_directory
):
    """Check if ValueError is wrapped correctly when adding same remote twice."""
    repo = GitRepo(empty_working_directory)
    new_remote_name = "new-remote"
    mocker.patch.object(repo._repo.remotes, "create", side_effect=[True, ValueError])
    repo.add_remote(new_remote_name, "https://git.fake-remote-url.local")

    with pytest.raises(GitError) as ge:
        repo.add_remote(new_remote_name, "https://git.fake-remote-url.local")
    assert ge.value.details == f"remote '{new_remote_name}' already exists."


def test_check_git_repo_add_remote_pygit_error_is_wrapped(
    mocker, empty_working_directory
):
    """Check if ValueError is wrapped correctly when adding same remote twice."""
    repo = GitRepo(empty_working_directory)
    new_remote_name = "new-remote"
    mocker.patch.object(repo._repo.remotes, "create", side_effect=pygit2.GitError)

    with pytest.raises(GitError) as ge:
        repo.add_remote(new_remote_name, "https://git.fake-remote-url.local")
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
