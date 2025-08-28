# This file is part of craft-application.
#
# Copyright 2023 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU Lesser General Public License version 3, as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for internal path utilities."""

import pathlib
import shutil

import pytest
from craft_application import util
from craft_application.util.paths import get_filename_from_url_path
from hypothesis import given, provisional


def test_get_managed_logpath(app_metadata):
    logpath = util.get_managed_logpath(app_metadata)

    assert isinstance(logpath, pathlib.PosixPath)
    assert str(logpath) == "/tmp/testcraft.log"


@given(url=provisional.urls())
def test_get_filename_from_url_path(url):
    """Test that it works with hypothesis-generated URLs"""
    get_filename_from_url_path(url)


@pytest.mark.parametrize(
    ("url", "filename"),
    [
        ("http://localhost/some/file.html?thing=stuff#anchor", "file.html"),
        ("http://localhost", ""),
    ],
)
def test_get_filename_from_url_path_correct(url, filename):
    assert get_filename_from_url_path(url) == filename


def test_get_work_dir_on_host(tmp_path):
    assert util.get_work_dir(tmp_path) == tmp_path


@pytest.mark.usefixtures("destructive_mode")
def test_get_work_dir_destructive(tmp_path):
    assert util.get_work_dir(tmp_path) == tmp_path


@pytest.mark.usefixtures("managed_mode")
def test_get_work_dir_managed(tmp_path):
    expected = pathlib.Path("/root")
    assert util.get_work_dir(tmp_path) == expected
    assert tmp_path != expected


def test_get_home_temporary_directory():
    temp_dir = util.get_home_temporary_directory()

    try:
        assert temp_dir.is_dir()
        assert temp_dir.relative_to(pathlib.Path.home())
        assert temp_dir.name.endswith(".tmp-craft")
    finally:
        shutil.rmtree(temp_dir)
