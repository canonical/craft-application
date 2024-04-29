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
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for grammar-aware project models."""

from craft_application.models import get_grammar_aware_part_keywords


def test_get_grammar_aware_part_keywords():
    """Test get_grammar_aware_part_keywords."""
    assert get_grammar_aware_part_keywords() == [
        "plugin",
        "source",
        "source-checksum",
        "source-branch",
        "source-commit",
        "source-depth",
        "source-subdir",
        "source-submodules",
        "source-tag",
        "source-type",
        "disable-parallel",
        "after",
        "overlay-packages",
        "stage-snaps",
        "stage-packages",
        "build-snaps",
        "build-packages",
        "build-environment",
        "build-attributes",
        "organize",
        "overlay",
        "stage",
        "prime",
        "override-pull",
        "overlay-script",
        "override-build",
        "override-stage",
        "override-prime",
        "permissions",
        "parse-info",
    ]
