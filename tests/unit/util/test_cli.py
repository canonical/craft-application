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

from datetime import datetime, timedelta, timezone

import pytest

from craft_application.util import format_timestamp

pytestmark = [
    pytest.mark.filterwarnings(
        "ignore:Timezone-naive datetime used. Replace with a timezone-aware one if possible.",
    )
]


@pytest.mark.parametrize(
    ("dt_obj", "expected"),
    [
        (
            datetime(2024, 5, 23, 13, 24, 0),
            "2024-05-23T13:24:00Z",
        ),
        (
            datetime(2024, 5, 23, 13, 24, 0, tzinfo=timezone.utc),
            "2024-05-23T13:24:00Z",
        ),
        (
            datetime(2024, 5, 23, 13, 24, 0, tzinfo=timezone(timedelta(hours=-5))),
            "2024-05-23T18:24:00Z",
        ),
    ],
)
def test_timezone_parsing(dt_obj: datetime, expected: str) -> None:
    assert format_timestamp(dt=dt_obj) == expected
