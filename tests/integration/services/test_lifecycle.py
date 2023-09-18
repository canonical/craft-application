# This file is part of craft_application.
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
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Integration tests for parts lifecycle."""

import pytest
import pytest_check
from craft_application.services.lifecycle import LifecycleService


@pytest.fixture(
    params=[
        pytest.param({"my-part": {"plugin": "nil"}}, id="basic"),
        pytest.param(
            {"my-part": {"plugin": "nil"}, "your-part": {"plugin": "nil"}},
            id="two-parts",
        ),
    ]
)
def parts_lifecycle(app_metadata, fake_project, fake_services, tmp_path, request):
    fake_project.parts = request.param

    return LifecycleService(
        app_metadata,
        fake_project,
        fake_services,
        work_dir=tmp_path / "work",
        cache_dir=tmp_path / "cache",
    )


def test_run_and_clean_all_parts(parts_lifecycle, emitter, check, tmp_path):
    parts_lifecycle.run("prime")

    with check:
        emitter.assert_trace("Planning prime for all parts")

    emitter.interactions = []

    parts_lifecycle.clean()

    with check:
        emitter.assert_progress("Cleaning all parts")

    pytest_check.is_false([*(tmp_path / "work").iterdir()])


def test_run_and_clean_my_part(parts_lifecycle, emitter, check):
    parts_lifecycle.run("prime", ["my-part"])

    with check:
        emitter.assert_trace("Planning prime for ['my-part']")

    emitter.interactions = []

    parts_lifecycle.clean(["my-part"])

    with check:
        emitter.assert_progress("Cleaning parts: my-part")
