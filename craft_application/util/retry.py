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

_ATTEMPT_COUNT = 4


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
    for attempt in range(_ATTEMPT_COUNT):
        emit.debug(
            f"Trying to {action_message} (attempt {attempt + 1}/{_ATTEMPT_COUNT})"
        )
        try:
            return call_to_retry(*call_args, **call_kwargs)
        except retry_exception as err:
            emit.debug(str(err))
            if attempt >= _ATTEMPT_COUNT - 1:
                raise
            time.sleep(3)
            continue

    raise AssertionError("This code is unreachable!")
