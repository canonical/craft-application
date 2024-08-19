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


class MyError(Exception):
    pass


def never_raises(*_args, **_kwargs) -> str:
    return "success"


def always_raises(*_args, **_kwargs) -> None:
    raise MyError("raised an error!")


@pytest.fixture
def mocked_sleep(mocker):
    return mocker.patch.object(time, "sleep")


def test_retry_success(mocked_sleep, emitter):
    assert retry("call never_raises", MyError, never_raises) == "success"

    # sleep() is not called.
    assert not mocked_sleep.called

    # Attempts get logged.
    emitter.assert_debug("Trying to call never_raises (attempt 1/6)")


def test_retry_args_kwargs():
    def full_func(*args, **kwargs) -> str:
        return f"{args}, {kwargs}"

    result = retry("call full_func", Exception, full_func, 1, 2, 3, val=True)

    assert result == "(1, 2, 3), {'val': True}"


@pytest.mark.parametrize("exceptions", [MyError, (ValueError, MyError)])
def test_retry_failure(mocked_sleep, exceptions, emitter):
    func_calls = 0

    def count_calls(*_args, **_kwargs):
        nonlocal func_calls
        func_calls += 1
        return always_raises()

    with pytest.raises(MyError):
        retry("call count_calls", exceptions, count_calls)

    # sleep() is called 5 times.
    assert mocked_sleep.mock_calls == [call(2), call(4), call(8), call(16), call(32)]

    # count_calls() is called 6 times (one more than sleep()).
    assert func_calls == len(mocked_sleep.mock_calls) + 1

    # Attempts get logged.
    emitter.assert_debug("Trying to call count_calls (attempt 1/6)")
    emitter.assert_debug("Trying to call count_calls (attempt 2/6)")
    emitter.assert_debug("Trying to call count_calls (attempt 3/6)")
    emitter.assert_debug("Trying to call count_calls (attempt 4/6)")
    emitter.assert_debug("Trying to call count_calls (attempt 5/6)")
    emitter.assert_debug("Trying to call count_calls (attempt 6/6)")


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
    assert mocked_sleep.mock_calls == [call(2), call(4)]
    emitter.assert_debug("Trying to call fails_twice (attempt 1/6)")
    emitter.assert_debug("Trying to call fails_twice (attempt 2/6)")


def test_retry_wrong_exception(mocked_sleep):
    with pytest.raises(MyError):
        retry("call always_raises", ValueError, always_raises)

    assert not mocked_sleep.called
