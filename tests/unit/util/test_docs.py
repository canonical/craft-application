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
    ("url", "version", "expected"),
    [
        # Cases with precise versions (must use the version)
        ("www.doc.com/tool/en/{version}", "1.0.0", "www.doc.com/tool/en/1.0.0"),
        ("www.doc.com/tool/{version}/a", "1.2.3", "www.doc.com/tool/1.2.3/a"),
        # Cases with interim versions (must use "latest")
        # craft-application style
        (
            "www.doc.com/tool/en/{version}",
            "3.1.0.post1+gb99d1e8",
            "www.doc.com/tool/en/latest",
        ),
        # Snapcraft style
        (
            "www.doc.com/tool/en/{version}",
            "8.3.1.post5+gitfb1834ce",
            "www.doc.com/tool/en/latest",
        ),
        # fallback "dev" version
        ("www.doc.com/tool/{version}", "dev", "www.doc.com/tool/latest"),
        # Cases with no {version} variable (must be a passthrough)
        ("www.doc.com/tool/en/latest", "1.0.0", "www.doc.com/tool/en/latest"),
        ("www.doc.com/tool/en/stable", "1.0.0", "www.doc.com/tool/en/stable"),
    ],
)
def test_render_doc_url(url, version, expected):
    obtained = docs.render_doc_url(url, version)
    assert obtained == expected
