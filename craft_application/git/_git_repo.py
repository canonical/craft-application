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

"""Git repository class and helper utilities."""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import time
from functools import lru_cache
from pathlib import Path
from shlex import quote
from typing import Final, cast

from craft_parts.utils import os_utils
from typing_extensions import Self

# Cannot catch the pygit2 error here raised by the global use of
# pygit2.Settings on import. We would ideally use pygit2.Settings
# for this
try:
    import pygit2  # type: ignore[import-untyped]
except Exception:  # noqa: BLE001 (narrower types are provided by the import)
    # This environment comes from ssl.get_default_verify_paths
    _old_env = os.getenv("SSL_CERT_DIR")
    # Needs updating when the base changes for applications' snap
    os.environ["SSL_CERT_DIR"] = "/snap/core22/current/etc/ssl/certs"
    import pygit2  # type: ignore[import-untyped]

    # Restore the environment in case the application shells out and the
    # environment that was setup is required.
    if _old_env is not None:
        os.environ["SSL_CERT_DIR"] = _old_env
    else:
        del os.environ["SSL_CERT_DIR"]

from ._consts import CRAFTGIT_BINARY_NAME, GIT_FALLBACK_BINARY_NAME, NO_PUSH_URL
from ._errors import GitError
from ._models import Commit, GitType, short_commit_sha

logger = logging.getLogger(__name__)

COMMIT_REGEX: Final[re.Pattern[str]] = re.compile("[0-9a-f]{40}")
SHORT_COMMIT_REGEX: Final[re.Pattern[str]] = re.compile("[0-9a-f]{7}")


def is_commit(ref: str) -> bool:
    """Check if given commit is a valid git commit sha."""
    return bool(COMMIT_REGEX.fullmatch(ref))


def is_short_commit(ref: str) -> bool:
    """Check if given short commit is a valid git commit sha."""
    return bool(SHORT_COMMIT_REGEX.fullmatch(ref))


def is_repo(path: Path) -> bool:
    """Check if a directory is a git repo.

    :param path: filepath to check

    :returns: True if path is a git repo.

    :raises GitError: if git fails while checking for a repository
    """
    # `path.absolute().parent` prevents pygit2 from checking parent directories
    try:
        return bool(
            pygit2.discover_repository(
                str(path),
                False,  # noqa: FBT003 (pygit2 doesn't accept keyword args here)
                str(path.absolute().parent),
            )
        )
    except pygit2.GitError as error:
        raise GitError(
            f"Could not check for git repository in {str(path)!r}."
        ) from error


def get_git_repo_type(path: Path) -> GitType:
    """Check if a directory is a git repo and return the type.

    :param path: filepath to check

    :returns: GitType
    """
    if is_repo(path):
        repo = pygit2.Repository(path.as_posix())
        if repo.is_shallow:
            return GitType.SHALLOW
        return GitType.NORMAL

    return GitType.INVALID


def parse_describe(describe_str: str) -> str:
    """Parse git describe string to get a human-readable version.

    Examples (git describe -> parse_describe):
    4.1.1-0-gad012482d -> 4.1.1
    4.1.1-16-g2d8943dbc -> 4.1.1.post16+git2d8943dbc
    curl-8_11_0-0-gb1ef0e1 -> curl-8_11_0

    For shallow clones or repositories missing tags:
    0ae7c04 -> 0ae7c04
    """
    if "-" not in describe_str:
        return describe_str
    number_of_expected_elements = 3
    splitted_describe = describe_str.rsplit(
        "-",
        maxsplit=number_of_expected_elements - 1,
    )
    if len(splitted_describe) != number_of_expected_elements:
        logger.warning("Cannot determine version basing on describe result.")
        return describe_str

    version, distance, commit = splitted_describe

    if distance == "0":
        return version
    return f"{version}.post{distance}+git{commit[1:]}"


class GitRepo:
    """Git repository class."""

    def __init__(self, path: Path) -> None:
        """Initialize a git repo.

        If a git repo does not already exist, a new repo will be initialized.

        :param path: filepath of the repo

        :raises FileNotFoundError: if the directory does not exist
        :raises GitError: if the repo cannot be initialized
        """
        self.path = path

        if not path.is_dir():
            raise FileNotFoundError(
                f"Could not initialize a git repository because {str(path)!r} does not "
                "exist or is not a directory."
            )

        if not is_repo(path):
            self._init_repo()

        self._repo = pygit2.Repository(path.as_posix())

    def add_all(self) -> None:
        """Add all changes from the working tree to the index.

        :raises GitError: if the changes could not be added
        """
        logger.debug("Adding all changes.")

        try:
            self._repo.index.add_all()  # pyright: ignore[reportUnknownMemberType]
            self._repo.index.write()  # pyright: ignore[reportUnknownMemberType]
        except pygit2.GitError as error:
            raise GitError(
                f"Could not add changes for the git repository in {str(self.path)!r}."
            ) from error

    def commit(self, message: str = "auto commit") -> str:
        """Commit changes to the repo.

        :param message: the commit message

        :returns: object ID of the commit as str

        :raises GitError: if the commit could not be created
        """
        logger.debug("Committing changes.")

        try:
            tree = (
                self._repo.index.write_tree()  # pyright: ignore[reportUnknownMemberType]
            )
        except pygit2.GitError as error:
            raise GitError(
                f"Could not create a tree for the git repository in {str(self.path)!r}."
            ) from error

        author = pygit2.Signature("auto commit", "auto commit")

        # a target is not needed for an unborn head (no existing commits in branch)
        target = [] if self._repo.head_is_unborn else [self._repo.head.target]

        try:
            return str(
                self._repo.create_commit("HEAD", author, author, message, tree, target)
            )
        except pygit2.GitError as error:
            raise GitError(
                "Could not create a commit for the git repository "
                f"in {str(self.path)!r}."
            ) from error

    def get_last_commit(self) -> Commit:
        """Get the last Commit on the current head."""
        try:
            last_commit = self._repo[self._repo.head.target]
        except pygit2.GitError as error:
            raise GitError("could not retrieve last commit") from error
        else:
            commit_message = cast(
                str,
                last_commit.message,  # pyright: ignore[reportAttributeAccessIssue,reportUnknownMemberType]
            )
            return Commit(
                sha=str(last_commit.id),
                message=commit_message,
            )

    def get_last_commit_on_branch_or_tag(
        self,
        branch_or_tag: str,
        *,
        remote: str | None = None,
        fetch: bool = False,
    ) -> Commit:
        """Find last commit corresponding to given branch or tag."""
        if fetch and remote is not None:
            self.fetch(remote=remote, tags=True)
        rev_list_output = [
            self.get_git_command(),
            "rev-list",
            "-n",
            "1",
            branch_or_tag,
        ]
        try:
            rev_parse_output = subprocess.check_output(
                rev_list_output,
                text=True,
                stderr=subprocess.STDOUT,
            )
        except subprocess.CalledProcessError as error:
            error_details = (
                f"cannot find ref: {branch_or_tag!r}.\nCommand output:\n{error.stdout}"
            )
            raise GitError(error_details) from error

        commit_sha = rev_parse_output.strip()
        try:
            commit_obj = self._repo.get(commit_sha)
        except (pygit2.GitError, ValueError) as error:
            raise GitError(
                f"cannot find commit: {short_commit_sha(commit_sha)!r}"
            ) from error
        else:
            commit_message = cast(
                str,
                commit_obj.message,  # pyright: ignore[reportOptionalMemberAccess,reportAttributeAccessIssue,reportUnknownMemberType]
            )
            return Commit(
                sha=commit_sha,
                message=commit_message,
            )

    def is_clean(self) -> bool:
        """Check if the repo is clean.

        :returns: True if the repo is clean.

        :raises GitError: if git fails while checking if the repo is clean
        """
        try:
            # for a clean repo, `status()` will return an empty dict
            return not bool(self._repo.status())
        except pygit2.GitError as error:
            raise GitError(
                f"Could not check if the git repository in {str(self.path)!r} is clean."
            ) from error

    def _init_repo(self) -> None:
        """Initialize a git repo.

        :raises GitError: if the repo cannot be initialized
        """
        logger.debug("Initializing git repository in %r", str(self.path))

        try:
            pygit2.init_repository(  # pyright: ignore[reportUnknownMemberType]
                self.path
            )
        except pygit2.GitError as error:
            raise GitError(
                f"Could not initialize a git repository in {str(self.path)!r}."
            ) from error

    def remote_exists(self, remote_name: str) -> bool:
        """Check if remote with given name is configured locally.

        :param remote_name: the remote repository name
        """
        try:
            _ = self._repo.remotes[remote_name]
        except KeyError:
            return False
        else:
            return True

    def add_remote(
        self,
        remote_name: str,
        remote_url: str,
    ) -> None:
        """Add remote in the repository configuration.

        :param remote_name: the remote repository name
        :param remote_url: the remote repository URL

        :raises GitError: if remote cannot be created
        """
        try:
            self._repo.remotes.create(remote_name, remote_url)
        except ValueError as error:
            raise GitError(f"remote '{remote_name}' already exists.") from error
        except pygit2.GitError as error:
            raise GitError(
                f"could not add remote to a git repository in {str(self.path)!r}."
            ) from error

    def rename_remote(
        self,
        remote_name: str,
        new_remote_name: str,
    ) -> None:
        """Rename remote in the repository configuration.

        :param remote_name: the remote repository name
        :param new_remote_name: the new name for the remote

        :raises GitError: if remote cannot be renamed
        """
        logger.debug("Renaming '%s' to '%s'", remote_name, new_remote_name)
        try:
            self._repo.remotes.rename(remote_name, new_remote_name)
        except KeyError as error:
            raise GitError(f"remote '{remote_name}' does not exist.") from error
        except ValueError as error:
            raise GitError(
                f"wrong name '{new_remote_name}' for the remote provided."
            ) from error
        except pygit2.GitError as error:
            raise GitError(
                f"cannot rename '{remote_name}' to '{new_remote_name}'"
            ) from error

    def get_remote_url(self, remote_name: str) -> str:
        """Get URL associated with the given remote.

        Equivalent of git remote get-url <name>


        :param remote_name: the remote repository name

        :raises GitError: if remote does not exist
        """
        if not self.remote_exists(remote_name=remote_name):
            raise GitError(f"cannot get URL for non-existing remote '{remote_name}'")
        return cast(str, self._repo.remotes[remote_name].url)

    def set_remote_url(self, remote_name: str, remote_url: str) -> None:
        """Set new URL for the existing remote.

        Equivalent of git remote set-url <name> <url>


        :param remote_name: the remote repository name
        :param remote_url: URL to be associated with the given remote

        :raises GitError: if remote does not exist
        """
        if not self.remote_exists(remote_name=remote_name):
            raise GitError(f"cannot set URL for non-existing remote: {remote_name!r}")
        self._repo.remotes.set_url(remote_name, remote_url)

    def get_remote_push_url(self, remote_name: str) -> str:
        """Get push-only URL associated with the given remote.

        Equivalent of git remote get-url --push <name>

        :param remote_name: the remote repository name

        :raises GitError: if remote does not exist
        """
        if not self.remote_exists(remote_name=remote_name):
            raise GitError(
                f"cannot get push URL for non-existing remote: {remote_name!r}"
            )
        return cast(str, self._repo.remotes[remote_name].push_url)

    def set_remote_push_url(self, remote_name: str, remote_push_url: str) -> None:
        """Set new push-only URL for the existing remote.

        Equivalent of git remote set-url --push <name> <url>


        :param remote_name: the remote repository name
        :param remote_url: push URL to be associated with the given remote

        :raises GitError: if remote does not exist
        """
        if not self.remote_exists(remote_name=remote_name):
            raise GitError(
                f"cannot set push URL for non-existing remote: {remote_name!r}"
            )
        self._repo.remotes.set_push_url(remote_name, remote_push_url)

    def set_no_push(self, remote_name: str) -> None:
        """Disable pushing to the selected remote.

        :param remote_name: the remote repository name

        :raises GitError: if remote does not exist
        """
        self.set_remote_push_url(remote_name, NO_PUSH_URL)

    def push_url(  # noqa: PLR0912 (too-many-branches)
        self,
        remote_url: str,
        remote_branch: str,
        ref: str = "HEAD",
        token: str | None = None,
        *,
        push_tags: bool = False,
    ) -> None:
        """Push a reference to a branch on a remote url.

        :param remote_url: the remote repo URL to push to
        :param remote_branch: the branch on the remote to push to
        :param ref: name of shorthand ref to push (i.e. a branch, tag, or `HEAD`)
        :param token: token in the url to hide in logs and errors
        :param push_tags: if true, push all tags to URL (similar to `git push --tags`)

        :raises GitError: if the ref cannot be resolved or pushed
        """
        resolved_ref = self._resolve_ref(ref)
        refspec = f"{resolved_ref}:refs/heads/{remote_branch}"

        # hide secret tokens embedded in a url
        stripped_url = remote_url.replace(token, "<token>") if token else remote_url

        logger.debug(
            "Pushing %r to remote %r with refspec %r.", ref, stripped_url, refspec
        )

        # temporarily call git directly due to libgit2 bug that unable to push
        # large repos using https. See https://github.com/libgit2/libgit2/issues/6385
        # and https://github.com/snapcore/snapcraft/issues/4478
        # Force push in case this repository already exists. The repository is always
        # going to exist solely for remote builds, so the only potential issue here is a
        # race condition with multiple remote builds on the same machine.
        cmd: list[str] = [
            self.get_git_command(),
            "push",
            "--force",
            remote_url,
            refspec,
            "--progress",
        ]
        if push_tags:
            cmd.append("--tags")

        git_proc: subprocess.Popen[str] | None = None
        try:
            with subprocess.Popen(
                cmd,
                cwd=str(self.path),
                bufsize=1,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True,
            ) as git_proc:
                # do not block on reading from the pipes
                # (has no effect on Windows until Python 3.12, so the readline() method is
                # blocking on Windows but git will still proceed)
                if git_proc.stdout:
                    os.set_blocking(git_proc.stdout.fileno(), False)
                if git_proc.stderr:
                    os.set_blocking(git_proc.stderr.fileno(), False)

                git_stdout: str
                git_stderr: str

                while git_proc.poll() is None:
                    if git_proc.stdout:
                        while git_stdout := git_proc.stdout.readline():
                            logger.info(git_stdout.rstrip())
                    if git_proc.stderr:
                        while git_stderr := git_proc.stderr.readline():
                            logger.error(git_stderr.rstrip())
                    # avoid too much looping, but not too slow to display progress
                    time.sleep(0.01)

        except subprocess.SubprocessError as error:
            # logging the remaining output
            if git_proc:
                if git_proc.stdout:
                    for git_stdout in git_proc.stdout.readlines():
                        logger.info(git_stdout.rstrip())
                if git_proc.stderr:
                    for git_stderr in git_proc.stderr.readlines():
                        logger.error(git_stderr.rstrip())  # noqa: TRY400

            raise GitError(
                f"Could not push {ref!r} to {stripped_url!r} with refspec {refspec!r} "
                f"for the git repository in {str(self.path)!r}: "
                f"{error!s}"
            ) from error

        if git_proc:
            git_proc.wait()
            if git_proc.returncode == 0:
                return

        raise GitError(
            f"Could not push {ref!r} to {stripped_url!r} with refspec {refspec!r} "
            f"for the git repository in {str(self.path)!r}."
        )

    def fetch(
        self,
        *,
        remote: str,
        tags: bool = False,
        ref: str | None = None,
        depth: int | None = None,
    ) -> None:
        """Fetch the contents of the given remote.

        :param remote: The name of the remote.
        :param tags: Whether to fetch tags.
        :param ref: Optional reference to the specific object to fetch.
        :param depth: Maximum number of commits to fetch (all by default).
        """
        fetch_command = [self.get_git_command(), "fetch"]

        if not self.remote_exists(remote):
            raise GitError(f"cannot fetch undefined remote: {remote!r}")

        if tags:
            fetch_command.append("--tags")
        if depth is not None:
            fetch_command.extend(["--depth", f"{depth}"])

        fetch_command.append(remote)
        if ref is not None:
            fetch_command.append(ref)

        try:
            os_utils.process_run(fetch_command, logger.debug)
        except FileNotFoundError as error:
            raise GitError("git command not found in the system") from error
        except subprocess.CalledProcessError as error:
            raise GitError(f"cannot fetch remote: {remote!r}") from error

    def remote_contains(
        self,
        *,
        remote: str,
        commit_sha: str,
    ) -> bool:
        """Check if the given commit is pushed to the remote repository."""
        logger.debug(
            "Checking if %r was pushed to %r", short_commit_sha(commit_sha), remote
        )
        checking_command = [
            self.get_git_command(),
            "branch",
            "--remotes",
            "--contains",
            commit_sha,
        ]
        try:
            remotes_that_has_given_commit = subprocess.check_output(
                checking_command,
                text=True,
            )
        except subprocess.CalledProcessError as error:
            raise GitError("incorrect commit provided, cannot check") from error
        else:
            for line in remotes_that_has_given_commit.splitlines():
                if line.strip().startswith(f"{remote}/"):
                    return True
        return False

    def describe(
        self,
        *,
        committish: str | None = None,
        abbreviated_size: int | None = None,
        always_use_long_format: bool | None = None,
        show_commit_oid_as_fallback: bool | None = None,
    ) -> str:
        """Return a human readable name base on an available ref.

        :param committish: Commit-ish object name to describe. If None, HEAD will be
        described
        :param abbreviated_size: The same as --abbrev of ``git describe`` command
        :param always_use_long_format: Always use the long format
        :param show_commit_oid_as_fallback: Show uniquely abbrevaited commit as fallback

        :returns: String that describes given object.

        raises GitError: if object cannot be described
        """
        logger.debug(f"Trying to describe {committish or 'HEAD'!r}.")
        try:
            described: str = self._repo.describe(
                committish=committish,
                abbreviated_size=abbreviated_size,
                always_use_long_format=always_use_long_format,
                show_commit_oid_as_fallback=show_commit_oid_as_fallback,
            )
        except (pygit2.GitError, KeyError) as err:
            raise GitError("Could not describe given object") from err
        else:
            return described

    def _resolve_ref(self, ref: str) -> str:
        """Get a full reference name for a shorthand ref.

        :param ref: shorthand ref name (i.e. a branch, tag, or `HEAD`)

        :returns: the full ref name (i.e. `refs/heads/main`)

        raises GitError: if the name could not be resolved
        """
        try:
            reference = str(self._repo.lookup_reference_dwim(ref).name)
        # raises a KeyError if the ref does not exist and a GitError for git errors
        except (pygit2.GitError, KeyError) as error:
            raise GitError(
                f"Could not resolve reference {ref!r} for the git repository in "
                f"{str(self.path)!r}."
            ) from error
        logger.debug("Resolved reference %r for name %r", reference, ref)
        return reference

    @classmethod
    def clone_repository(
        cls,
        *,
        url: str,
        path: Path,
        checkout_branch: str | None = None,
        depth: int = 0,
        single_branch: bool = False,
    ) -> Self:
        """Clone repository to specific path and return GitRepo object.

        :param url: the URL to clone repository from
        :param path: path to the directory where repository should be cloned
        :param checkout_branch: optional branch which should be checked out
        :param depth: optional parameter to specify history len of the clone
        :param single_branch: optional to narrow cloning to the single branch

        :returns: GitRepo wrapper around the repository

        raises GitError: if cloning repository cannot be done
        """
        if is_repo(path):
            raise GitError("Cannot clone to existing repository")

        logger.debug("Cloning %s to %s", url, path)
        clone_cmd = [cls.get_git_command(), "clone"]
        if checkout_branch is not None:
            logger.debug("Checking out to branch: %s", checkout_branch)
            clone_cmd.extend(["--branch", quote(checkout_branch)])
        if depth > 0:
            logger.debug("Limiting to last %d commits", depth)
            clone_cmd.extend(["--depth", str(depth)])
        if single_branch:
            logger.debug("Limiting to the single branch")
            clone_cmd.append("--single-branch")
        clone_cmd.extend([url, os.fspath(path)])

        try:
            os_utils.process_run(clone_cmd, logger.debug)
        except FileNotFoundError as error:
            raise GitError("git command not found in the system") from error
        except subprocess.CalledProcessError as error:
            raise GitError(
                f"cannot clone repository: {url} to {str(path)!r}"
            ) from error
        return cls(path)

    @classmethod
    @lru_cache(maxsize=1)
    def get_git_command(cls) -> str:
        """Get name of the git executable that may be used in subprocesses.

        Fallback to the previous behavior in case of non-snap / local installation or
        if snap does not provide expected binary.
        """
        craftgit_binary = CRAFTGIT_BINARY_NAME
        if shutil.which(craftgit_binary):
            return craftgit_binary
        logger.warning(
            "Cannot find craftgit binary: %r. Is it a part of snap package?",
            craftgit_binary,
        )
        logger.warning("Falling back to: %r", GIT_FALLBACK_BINARY_NAME)
        return GIT_FALLBACK_BINARY_NAME
