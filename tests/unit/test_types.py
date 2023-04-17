#  This file is part of craft-application.
#
#  2023 Canonical Ltd.
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
"""Tests for craft-application constrained types."""
import re
from string import ascii_lowercase, digits

import pytest
from craft_application.types import ProjectName
from hypothesis import given
from hypothesis.strategies import composite, sampled_from, text

LOWER_ALPHA_NUMERIC = [*ascii_lowercase, *digits]


# region Compliance tests for regular expressions used in constraints.
@composite
def valid_project_name_strategy(draw):
    """A strategy for a project name that matches all the project name rules:

    * Valid characters are lower-case ASCII letters, numerals and hyphens.
    * Must contain at least one letter
    * May not start or end with a hyphen
    * May not have two hyphens in a row
    """
    strategy = text(sampled_from([*LOWER_ALPHA_NUMERIC, "-"]), min_size=1, max_size=40)
    filtered = strategy.filter(
        lambda name: all(
            (
                "--" not in name,
                not (name.startswith("-") or name.endswith("-")),
                re.match("[a-z]", name),
            )
        )
    )
    return draw(filtered)


@given(valid_project_name_strategy())
def test_project_name_regex_valid_hypothesis(project_name):
    assert re.match(ProjectName.regex, project_name)


@pytest.mark.parametrize("name", ["", "1", "-", "-abc", "abc123-", "double--hyphen"])
def test_invalid_project_name(name):
    assert not re.match(ProjectName.regex, name)


# endregion
