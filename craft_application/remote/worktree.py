# Copyright (C) 2019, 2023-2024 Canonical Ltd
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

"""Manages trees for remote builds."""

from pathlib import Path
from shutil import copytree
from typing import cast

from xdg import BaseDirectory  # type: ignore[import-untyped]

from craft_application.git import GitError, GitRepo

from .errors import RemoteBuildGitError
from .utils import rmtree


class WorkTree:
    """Class to manage trees for remote builds.

    :param app_name: Name of the application.
    :param build_id: Unique identifier for the build.
    :param project_dir: Path to project directory.
    """

    def __init__(self, app_name: str, build_id: str, project_dir: Path) -> None:
        self._project_dir = project_dir
        self._base_dir = Path(
            BaseDirectory.save_cache_path(app_name, "remote-build", build_id)
        )
        self._repo_dir = self._base_dir / "repo"

    @property
    def repo_dir(self) -> Path:
        """Get path the cached repository."""
        return self._repo_dir

    def init_repo(self) -> None:
        """Initialize a clean repo."""
        if self._repo_dir.exists():
            rmtree(self._repo_dir)

        copytree(self._project_dir, self._repo_dir)

        self._gitify_repository()

    def _gitify_repository(self) -> None:
        """Git-ify source repository tree."""
        try:
            repo = GitRepo(self._repo_dir)
            if not repo.is_clean():
                repo.add_all()
                repo.commit()
        except GitError as git_error:
            raise RemoteBuildGitError(
                cast(str, git_error.details),
            ) from git_error

    def clean_cache(self) -> None:
        """Clean the cache."""
        if self._base_dir.exists():
            rmtree(self._base_dir)
