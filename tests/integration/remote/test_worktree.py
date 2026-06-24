# Copyright (C) 2026 Canonical Ltd
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

"""Integration tests for the worktree module."""

import pytest
from craft_application.remote import WorkTree


@pytest.fixture(autouse=True)
def mock_git_repo(mocker):
    """Returns a mocked GitRepo."""
    return mocker.patch("craft_application.remote.worktree.GitRepo")


@pytest.fixture(autouse=True)
def mock_base_directory(mocker, tmp_path):
    _mock_base_directory = mocker.patch(
        "craft_application.remote.worktree.BaseDirectory"
    )
    _mock_base_directory.save_cache_path.return_value = tmp_path
    return _mock_base_directory


def test_init_repo_with_dangling_symlink(tmp_path):
    """Test that init_repo succeeds when the project contains a dangling symlink."""
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "testcraft.yaml").write_text("name: test\n")
    (project_dir / "broken-link").symlink_to(project_dir / "nonexistent")

    worktree = WorkTree(
        app_name="test-app", build_id="test-id", project_dir=project_dir
    )
    # Should not raise even though broken-link points to a nonexistent target
    worktree.init_repo()

    assert (worktree.repo_dir / "testcraft.yaml").is_file()
    assert not (worktree.repo_dir / "broken-link").is_symlink()
