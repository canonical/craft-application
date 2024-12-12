# This file is part of craft_application.
#
# Copyright 2024 Canonical Ltd.
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
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Unit tests for system util module."""

import pytest

from craft_application import util
from craft_application.errors import InvalidParameterError


@pytest.mark.parametrize(
    ("env_dict", "cpu_count", "expected"),
    [
        (
            {},
            None,
            1,
        ),
        (
            {},
            100,
            100,
        ),
        (
            {"TESTCRAFT_PARALLEL_BUILD_COUNT": "100"},
            1,
            100,
        ),
        (
            {"CRAFT_PARALLEL_BUILD_COUNT": "200"},
            1,
            200,
        ),
        (
            {
                "TESTCRAFT_MAX_PARALLEL_BUILD_COUNT": "100",
            },
            50,
            50,
        ),
        (
            {
                "CRAFT_MAX_PARALLEL_BUILD_COUNT": "100",
            },
            80,
            80,
        ),
        (
            {
                "TESTCRAFT_PARALLEL_BUILD_COUNT": "100",
                "CRAFT_PARALLEL_BUILD_COUNT": "200",
            },
            1,
            100,
        ),
        (
            {
                "TESTCRAFT_MAX_PARALLEL_BUILD_COUNT": "100",
                "CRAFT_MAX_PARALLEL_BUILD_COUNT": "200",
            },
            150,
            100,
        ),
        (
            {
                "TESTCRAFT_MAX_PARALLEL_BUILD_COUNT": "100",
                "CRAFT_MAX_PARALLEL_BUILD_COUNT": "200",
            },
            None,
            1,
        ),
        (
            {
                "TESTCRAFT_PARALLEL_BUILD_COUNT": "100",
                "CRAFT_PARALLEL_BUILD_COUNT": "200",
                "TESTCRAFT_MAX_PARALLEL_BUILD_COUNT": "300",
                "CRAFT_MAX_PARALLEL_BUILD_COUNT": "400",
            },
            150,
            100,
        ),
    ],
)
def test_get_parallel_build_count(monkeypatch, mocker, env_dict, cpu_count, expected):
    mocker.patch("os.cpu_count", return_value=cpu_count)
    for env_dict_key, env_dict_value in env_dict.items():
        monkeypatch.setenv(env_dict_key, env_dict_value)

    assert util.get_parallel_build_count("testcraft") == expected


@pytest.mark.parametrize(
    ("env_dict", "cpu_count"),
    [
        pytest.param(
            {
                "TESTCRAFT_PARALLEL_BUILD_COUNT": "abc",
            },
            1,
            id="abc",
        ),
        pytest.param(
            {
                "CRAFT_PARALLEL_BUILD_COUNT": "-",
            },
            1,
            id="-",
        ),
        pytest.param(
            {
                "TESTCRAFT_MAX_PARALLEL_BUILD_COUNT": "*",
            },
            1,
            id="*",
        ),
        pytest.param(
            {
                "CRAFT_MAX_PARALLEL_BUILD_COUNT": "$COUNT",
            },
            1,
            id="COUNT",
        ),
        pytest.param(
            {
                "TESTCRAFT_PARALLEL_BUILD_COUNT": "0",
            },
            1,
            id="0",
        ),
        pytest.param(
            {
                "CRAFT_PARALLEL_BUILD_COUNT": "-1",
            },
            1,
            id="-1",
        ),
        pytest.param(
            {
                "TESTCRAFT_MAX_PARALLEL_BUILD_COUNT": "5.6",
            },
            1,
            id="5.6",
        ),
        pytest.param(
            {
                "CRAFT_MAX_PARALLEL_BUILD_COUNT": "inf",
            },
            1,
            id="inf",
        ),
    ],
)
def test_get_parallel_build_count_error(monkeypatch, mocker, env_dict, cpu_count):

    mocker.patch("os.cpu_count", return_value=cpu_count)
    for env_dict_key, env_dict_value in env_dict.items():
        monkeypatch.setenv(env_dict_key, env_dict_value)

    with pytest.raises(
        InvalidParameterError, match=r"^Value '.*' is invalid for parameter '.*'.$"
    ):
        util.get_parallel_build_count("testcraft")
