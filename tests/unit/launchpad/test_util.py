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
"""Tests for utility functions."""
from unittest import mock

import pytest
from craft_application.launchpad import models, util
from hypothesis import given, strategies
from lazr.restfulclient.resource import Entry


@given(
    path=strategies.iterables(
        strategies.text().filter(lambda x: not x.startswith("__"))  # no mangled names
    )
)
def test_getattrs_success(path):
    obj = mock.Mock()

    actual = util.getattrs(obj, path)

    assert isinstance(actual, mock.Mock)


@pytest.mark.parametrize(
    ("obj", "path", "expected"),
    [
        ("", ["__class__", "__name__"], "str"),
        (format, ["__call__", "__call__", "__class__", "__class__"], type),
        (1, "real.imag.numerator.denominator.__class__", int),
    ],
)
def test_getattrs_success_examples(obj, path, expected):
    actual = util.getattrs(obj, path)

    assert actual == expected


@pytest.mark.parametrize(
    ("obj", "path", "partial_path"),
    [
        ("", "non_attribute", "non_attribute"),
        ("", "upper.not.an.attribute", "upper.not"),
    ],
)
def test_getattrs_exception(obj, path, partial_path):
    with pytest.raises(AttributeError) as exc_info:
        util.getattrs(obj, path)

    assert exc_info.value.name == partial_path
    assert exc_info.value.obj == obj


@pytest.mark.parametrize("value", ["someone", "/~someone", "/~someone/+snaps"])
def test_get_person_link_string_success(value):
    assert util.get_person_link(value) == "/~someone"


@pytest.mark.parametrize("resource_type", ["person", "team"])
def test_get_person_link_entry_success(resource_type):
    mock_entry = mock.Mock(spec=Entry)
    mock_entry.resource_type_link = f"http://blah/#{resource_type}"
    mock_entry.name = "someone"

    assert util.get_person_link(mock_entry) == "/~someone"


def test_get_person_link_entry_wrong_type():
    mock_entry = mock.Mock(spec=Entry, resource_type_link="http://blah/#poo")

    with pytest.raises(TypeError, match="Invalid resource type 'poo'"):
        util.get_person_link(mock_entry)


@pytest.mark.parametrize("arch", models.Architecture)
def test_get_architecture_passthrough(arch):
    assert util.get_architecture(arch.name) == arch
    assert util.get_architecture(arch.value) == arch


@pytest.mark.parametrize("arch", util.ARCHITECTURE_MAP.keys())
def test_get_architecture_map(arch):
    assert util.get_architecture(arch) in models.Architecture


@pytest.mark.parametrize("arch", ["gothic", "brutalist"])
def test_get_invalid_architecture(arch):
    with pytest.raises(ValueError, match=f"Unknown architecture {arch!r}"):
        util.get_architecture(arch)


@pytest.mark.parametrize("arch", ["AMD64", " x64 ", "          ARMhf"])
def test_get_architecture_string_manipulation(arch):
    assert util.get_architecture(arch) in models.Architecture
