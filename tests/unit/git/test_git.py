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
from unittest.mock import ANY

import pygit2
import pygit2.enums
import pytest
from craft_application.git import GitError, GitRepo, GitType, get_git_repo_type, is_repo
from craft_application.remote import (
    RemoteBuildInvalidGitRepoError,
    check_git_repo_for_remote_build,
)


@pytest.fixture()
def empty_working_directory(tmp_path) -> Iterator[Path]:
    cwd = pathlib.Path.cwd()

    repo_dir = Path(tmp_path, "test-repo")
    repo_dir.mkdir()
    os.chdir(repo_dir)
    yield repo_dir

    os.chdir(cwd)


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


def test_check_git_repo_for_remote_build_normal(empty_working_directory):
    """Check if directory is a repo."""
    GitRepo(empty_working_directory)
    check_git_repo_for_remote_build(empty_working_directory)


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
        match="Remote build for shallow cloned git repos are no longer supported",
    ):
        check_git_repo_for_remote_build(git_shallow_path)
