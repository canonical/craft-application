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
"""Tests for craft-application app classes."""
import craft_application
import pytest
import pytest_check
from craft_application.app import AppMetadata


@pytest.mark.parametrize("summary", ["A summary", None])
def test_app_metadata_post_init_correct(summary):
    app = AppMetadata("craft-application", summary)

    pytest_check.equal(app.version, craft_application.__version__)
    pytest_check.is_not_none(app.summary)
