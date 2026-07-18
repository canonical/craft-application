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
"""Tests for documentation functions."""

import pytest
from craft_application.util import docs


@pytest.mark.parametrize(
    ("url", "version", "major", "expected"),
    [
        # Cases with precise versions (must use the version)
        ("www.doc.com/tool/{version}", "1.0.0", True, "www.doc.com/tool/1"),
        ("www.doc.com/tool/{version}", "1.3.5", False, "www.doc.com/tool/1.3.5"),
        ("www.doc.com/tool/{version}/a", "2.4.6", True, "www.doc.com/tool/2/a"),
        # Cases with interim versions (must use "latest")
        # craft-application style
        (
            "www.doc.com/tool/{version}",
            "3.1.0.post1+gb99d1e8",
            True,
            "www.doc.com/tool/latest",
        ),
        # Snapcraft style
        (
            "www.doc.com/tool/{version}",
            "8.3.1.post5+gitfb1834ce",
            True,
            "www.doc.com/tool/latest",
        ),
        # fallback "dev" version
        ("www.doc.com/tool/{version}", "dev", True, "www.doc.com/tool/latest"),
        # Cases with no {version} variable (must be a passthrough)
        ("www.doc.com/tool/latest", "1.0.0", True, "www.doc.com/tool/latest"),
        ("www.doc.com/tool/stable", "1.0.0", True, "www.doc.com/tool/stable"),
    ],
)
def test_render_doc_url(url, version, major, expected):
    obtained = docs.render_doc_url(url, version, major)
    assert obtained == expected
