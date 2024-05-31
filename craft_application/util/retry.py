#  This file is part of craft-application.
#
#  Copyright 2024 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Utilities to retry fickle calls."""

import time
from typing import Any, Protocol, TypeVar

from craft_cli import emit

# The number of seconds to sleep after each consecutive retry failure.
# Added together, each call to retry() will sleep() at most just over a minute
# (62 seconds).
_ATTEMPT_SLEEPS = [2, 4, 8, 16, 32]


R_co = TypeVar("R_co", covariant=True)  # the variable return type


class RetryCallable(Protocol[R_co]):
    """Protocol for callables to be retried.

    The main purpose is to annotate the return type (R_co), so that ``retry``
    can declare that it returns whatever ``call_to_retry`` returns.
    """

    def __call__(self, *args: Any, **kwargs: Any) -> R_co:  # noqa: ANN401 (Use of Any)
        """Call the callable."""
        ...


def retry(
    action_message: str,
    retry_exception: type[Exception] | tuple[type[Exception], ...],
    call_to_retry: RetryCallable[R_co],
    /,
    *call_args: Any,  # noqa: ANN401 (Use of Any)
    **call_kwargs: Any,  # noqa: ANN401 (Use of Any)
) -> R_co:
    """Retry a flaky call multiple times.

    :param action_message: a short description of the call's intent, usually in
      the form <verb> <noun>, to log the retry attempts. Example: "create snap X".
    :param retry_exception: the exception, or group of exceptions, that can
      trigger a retry attempt. Any other exception will just be propagated up
      without retrying.
    :param call_to_retry: the callable to be retried.
    :param call_args: the args to be passed to when calling
      ``call_to_retry``.
    :param call_kwargs: the kwargs to be passed to when calling
      ``call_to_retry``.
    """
    total_attempts = len(_ATTEMPT_SLEEPS) + 1

    for attempt, sleep_time in enumerate(_ATTEMPT_SLEEPS, start=1):
        emit.debug(f"Trying to {action_message} (attempt {attempt}/{total_attempts})")
        try:
            return call_to_retry(*call_args, **call_kwargs)
        except retry_exception as err:
            emit.debug(str(err))
            time.sleep(sleep_time)
            continue

    # One final, sleep-less call to let the exception propagate.
    emit.debug(
        f"Trying to {action_message} (attempt {total_attempts}/{total_attempts})"
    )
    return call_to_retry(*call_args, **call_kwargs)
