# Copyright 2025 Canonical Ltd.
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


"""Tests for the pygit2 utils."""

import pathlib
import textwrap
from typing import cast

import pytest
from craft_application.git._utils import _FALLBACK_PATH, find_ssl_cert_dir
from pyfakefs import fake_filesystem


@pytest.fixture
def fake_snap_path(fs: fake_filesystem.FakeFilesystem) -> pathlib.Path:
    fake_path = pathlib.Path("/craft", "snap", "test", "current")
    fs.create_dir(fake_path)
    return fake_path


@pytest.fixture
def fake_snap_env(
    fake_snap_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SNAP", str(fake_snap_path))


@pytest.fixture(params=["core22", "core24", "core26"])
def fake_base(
    request: pytest.FixtureRequest,
    fake_snap_path: pathlib.Path,
    fake_snap_env: None,
    monkeypatch: pytest.MonkeyPatch,
) -> str:
    base = cast(str, request.param)
    write_metadata(
        fake_snap_path,
        textwrap.dedent(
            f"""\
            base: {base}
            """
        ),
    )
    return base


def write_metadata(snap_path: pathlib.Path, content: str) -> None:
    snap_metadata = snap_path / "meta" / "snap.yaml"
    snap_metadata.parent.mkdir()
    snap_metadata.write_text(content)


def test_import_fallback_in_non_snap_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fallback to previous one if not running as a snap."""
    monkeypatch.delenv("SNAP", raising=False)
    assert find_ssl_cert_dir() == _FALLBACK_PATH, (
        "Use fallback if not installed as a snap."
    )


@pytest.mark.usefixtures("fake_snap_env")
def test_import_fallback_missing_metadata() -> None:
    """Fallback to previous one if metadata is missing."""
    assert find_ssl_cert_dir() == _FALLBACK_PATH, (
        "Use fallback if not snap.yaml is missing."
    )


@pytest.mark.usefixtures("fake_snap_env")
def test_import_fallback_empty_metadata(fake_snap_path: pathlib.Path) -> None:
    """Fallback to previous one if metadata is empty."""
    write_metadata(fake_snap_path, "")
    assert find_ssl_cert_dir() == _FALLBACK_PATH, (
        "Should return fallback if base not available in snap.yaml."
    )


@pytest.mark.usefixtures("fake_snap_env")
def test_import_fallback_wrong_metadata(fake_snap_path: pathlib.Path) -> None:
    """Fallback to previous one if metadata is incorrect."""
    write_metadata(fake_snap_path, '{"i-am": "json"}')
    assert find_ssl_cert_dir() == _FALLBACK_PATH, (
        "Should return fallback if base not available in snap.yaml."
    )


def test_finding_correct_path_with_snap_metadata(fake_base: str) -> None:
    """SSL_CERT_DIR should be set accordingly to the requesting snap base"""
    assert find_ssl_cert_dir() == f"/snap/{fake_base}/current/etc/ssl/certs", (
        f"Incorrect SSL_CERT_DIR for base: {fake_base!r}"
    )
