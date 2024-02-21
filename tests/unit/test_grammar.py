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
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Unit tests for craft-application grammar process."""


import pydantic
import pytest
from craft_application.models.grammar import (
    GrammarAwareProject,
    _GrammarAwarePart,
)


@pytest.mark.parametrize(
    ("part"),
    [
        ({}),
        (
            {
                "plugin": "nil",
            }
        ),
        (
            {
                "source": ".",
            }
        ),
        (
            {
                "build-environment": [{"MESSAGE": "A"}, {"NAME": "B"}],
                "build-packages": ["C", "D"],
            }
        ),
        (
            {
                "build-snaps": ["G", "H"],
                "stage-snaps": ["I", "J"],
                "parse-info": ["K", "L"],
            }
        ),
        (
            {
                "parse-info": ["K", "L"],
            }
        ),
        (
            {
                "source": ".",
                "build-environment": [{"MESSAGE": "A"}, {"NAME": "B"}],
                "build-packages": ["C", "D"],
                "stage-packages": ["E", "F"],
                "build-snaps": ["G", "H"],
                "stage-snaps": ["I", "J"],
                "parse-info": ["K", "L"],
            }
        ),
        (
            {
                "source": ".",
                "build-environment": [{"MESSAGE": "A"}, {"NAME": "B"}],
                "build-packages": ["C", "D"],
                "stage-packages": ["E", "F"],
                "build-snaps": ["G", "H"],
                "stage-snaps": ["I", "J"],
                "parse-info": ["K", "L"],
                "extra": "extra",
            }
        ),
        (
            {
                "extra": "extra",
            }
        ),
    ],
)
def test_grammar_aware_part(part):
    """Test the grammar-aware part should be able to parse the input data."""
    _GrammarAwarePart(**part)


@pytest.mark.parametrize(
    ("part"),
    [
        (
            {
                "source": {},
            }
        ),
        (
            {
                "build-environment": [{"MESSAGE": "A", "NAME": "B"}],
            }
        ),
        (
            {
                "build-snaps": [None, "H"],
            }
        ),
        (
            {
                "parse-info": {"K": "L"},
            }
        ),
    ],
)
def test_grammar_aware_part_error(part):
    """Test the grammar-aware part should be able to report error."""
    with pytest.raises(pydantic.ValidationError):
        _GrammarAwarePart(**part)


@pytest.mark.parametrize(
    ("project"),
    [
        (
            {
                "name": "empty",
                "title": "A most basic project",
                "version": "git",
                "base": ["ubuntu", "22.04"],
                "parts": {"my-part": {"plugin": None}},
            }
        ),
        (
            {
                "name": "empty",
                "title": "A most basic project",
                "version": "git",
                "base": ["ubuntu", "22.04"],
                "parts": {"my-part": {"plugin": None}, "my-part2": {"plugin": None}},
            }
        ),
        (
            {
                "name": "empty",
                "title": "A most basic project",
                "version": "git",
                "base": ["ubuntu", "22.04"],
                "parts": {
                    "my-part": {
                        "source": ".",
                        "build-environment": [{"MESSAGE": "A"}, {"NAME": "B"}],
                        "build-packages": ["C", "D"],
                        "stage-packages": ["E", "F"],
                        "build-snaps": ["G", "H"],
                        "stage-snaps": ["I", "J"],
                        "parse-info": ["K", "L"],
                    }
                },
            }
        ),
        (
            {
                "name": "empty",
                "title": "A most basic project",
                "version": "git",
                "base": ["ubuntu", "22.04"],
                "parts": {
                    "my-part": {
                        "source": ".",
                        "build-environment": [{"MESSAGE": "A"}, {"NAME": "B"}],
                        "build-packages": ["C", "D"],
                        "stage-packages": ["E", "F"],
                        "build-snaps": ["G", "H"],
                        "stage-snaps": ["I", "J"],
                        "parse-info": ["K", "L"],
                    },
                    "my-part2": {
                        "source": ".",
                        "stage-packages": ["E", "F"],
                        "build-snaps": ["G", "H"],
                        "parse-info": ["K", "L"],
                        "extra": "extra",
                    },
                },
            }
        ),
        (
            {  # No "parts" defined - gets coerced to an empty dict of parts.
                "name": "empty",
                "title": "A most basic project",
                "version": "git",
                "base": ["ubuntu", "22.04"],
            }
        ),
        (
            {  # Same as above, but without coercion.
                "name": "empty",
                "title": "A most basic project",
                "version": "git",
                "base": ["ubuntu", "22.04"],
                "parts": {},
            }
        ),
    ],
)
def test_grammar_aware_project(project):
    """Test the grammar-aware part should be able to parse the input data."""
    GrammarAwareProject.validate_grammar(project)


@pytest.mark.parametrize(
    ("project"),
    [
        (
            {
                "name": "empty",
                "title": "A most basic project",
                "version": "git",
                "base": ["ubuntu", "22.04"],
                "parts": {
                    "my-part": {
                        "source": ".",
                        "build-environment": [{"MESSAGE": "A", "NAME": "B"}],
                        "build-packages": ["C", "D"],
                        "stage-packages": ["E", "F"],
                        "build-snaps": ["G", "H"],
                        "stage-snaps": ["I", "J"],
                        "parse-info": ["K", "L"],
                    }
                },
            }
        ),
        (
            {
                "name": "empty",
                "title": "A most basic project",
                "version": "git",
                "base": ["ubuntu", "22.04"],
                "parts": ["my-part"],
            }
        ),
        (
            {
                "name": "empty",
                "title": "A most basic project",
                "version": "git",
                "base": ["ubuntu", "22.04"],
                "parts": {None: {}},
            }
        ),
    ],
)
def test_grammar_aware_project_error(project):
    """Test the grammar-aware project should be able to report error."""
    with pytest.raises(pydantic.ValidationError):
        GrammarAwareProject.validate_grammar(project)
