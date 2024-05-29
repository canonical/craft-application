# This file is part of craft-application.
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
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests for retry()."""
import time
from unittest.mock import call

import pytest
from craft_application.util import retry

EXPECTED_ATTEMPTS = 3


class MyError(Exception):
    pass


def never_raises(*_args, **_kwargs) -> str:
    return "success"


def always_raises(*_args, **_kwargs) -> None:
    raise MyError("raised an error!")


@pytest.fixture()
def mocked_sleep(mocker):
    return mocker.patch.object(time, "sleep")


def test_retry_success(mocked_sleep, emitter):
    assert retry("call never_raises", MyError, never_raises) == "success"

    # sleep() is not called.
    assert not mocked_sleep.called

    # Attempts get logged.
    emitter.assert_debug("Trying to call never_raises (attempt 1/4)")


def test_retry_args_kwargs():
    def full_func(*args, **kwargs) -> str:
        return f"{args}, {kwargs}"

    result = retry("call full_func", Exception, full_func, 1, 2, 3, val=True)

    assert result == "(1, 2, 3), {'val': True}"


@pytest.mark.parametrize("exceptions", [MyError, (ValueError, MyError)])
def test_retry_failure(mocked_sleep, exceptions, emitter):
    with pytest.raises(MyError):
        retry("call always_raises", exceptions, always_raises)

    # sleep() is called multiple times.
    assert mocked_sleep.mock_calls == [call(3)] * EXPECTED_ATTEMPTS

    # Attempts get logged.
    emitter.assert_debug("Trying to call always_raises (attempt 1/4)")
    emitter.assert_debug("Trying to call always_raises (attempt 2/4)")
    emitter.assert_debug("Trying to call always_raises (attempt 3/4)")
    emitter.assert_debug("Trying to call always_raises (attempt 4/4)")


def test_retry_eventual_success(mocked_sleep, emitter):
    attempt = 0
    should_raise = [True, True, False]

    def fails_twice(*_args, **_kwargs):
        nonlocal attempt

        if should_raise[attempt]:
            attempt += 1
            raise MyError

        return "eventual success"

    result = retry("call fails_twice", MyError, fails_twice)

    assert result == "eventual success"
    assert mocked_sleep.mock_calls == [call(3), call(3)]
    emitter.assert_debug("Trying to call fails_twice (attempt 1/4)")
    emitter.assert_debug("Trying to call fails_twice (attempt 2/4)")


def test_retry_wrong_exception(mocked_sleep):
    with pytest.raises(MyError):
        retry("call always_raises", ValueError, always_raises)

    assert not mocked_sleep.called
