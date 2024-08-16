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
"""Basic Launchpad object tests."""

import enum
from collections.abc import Mapping
from typing import Any
from unittest import mock

import pytest
from craft_application.launchpad import Launchpad, LaunchpadObject
from lazr.restfulclient.resource import Entry
from typing_extensions import Self


class Type(enum.Enum):
    """Resource types for testing."""

    THIS = "this"
    VALID = "valid_type"
    NAME = "something"


class FakeLaunchpadObject(LaunchpadObject):
    """A Launchpad object for testing."""

    _resource_types = Type
    _attr_map: Mapping[str, str] = {}

    @classmethod
    def get(cls, *args: Any, **kwargs: Any) -> Self:
        raise NotImplementedError

    @classmethod
    def new(cls, *args: Any, **kwargs: Any) -> Self:
        raise NotImplementedError


@pytest.fixture
def fake_obj(fake_launchpad, mock_lplib_entry):
    return FakeLaunchpadObject(fake_launchpad, mock_lplib_entry)


@pytest.mark.parametrize("resource_type", [t.value for t in Type])
def test_init_success(resource_type):
    mock_entry = mock.Mock(spec=Entry, resource_type=resource_type)
    mock_entry.resource_type_link = f"https://localhost/#{resource_type}"
    mock_entry.lp_attributes = []
    mock_lp = mock.Mock(spec_set=Launchpad)

    FakeLaunchpadObject(mock_lp, mock_entry)


@pytest.mark.parametrize("resource_type", ["ThIs", "invalid_type", "NAME"])
def test_invalid_resource_type(resource_type, mock_lplib_entry):
    mock_lplib_entry.configure_mock(
        resource_type=resource_type,
        resource_type_link=f"https://localhost/#{resource_type}",
        lp_attributes=[],
    )
    mock_lp = mock.Mock(spec_set=Launchpad)

    with pytest.raises(
        TypeError,
        match="Launchpadlib entry not a valid resource type for",
    ):
        FakeLaunchpadObject(mock_lp, mock_lplib_entry)


def test_dir_annotations(fake_launchpad, mock_lplib_entry):
    class AnnotationsObject(FakeLaunchpadObject):
        some_attribute_right_here: str

    assert "some_attribute_right_here" in dir(
        AnnotationsObject(fake_launchpad, mock_lplib_entry)
    )


def test_dir_attr_map(fake_launchpad, mock_lplib_entry):
    class AttrMapObject(FakeLaunchpadObject):
        _attr_map = {"something": ""}

    assert "something" in dir(AttrMapObject(fake_launchpad, mock_lplib_entry))


def test_dir_lp_attributes(fake_obj, mock_lplib_entry):
    mock_lplib_entry.lp_attributes = ["abc", "def", "ghi"]

    assert {"abc", "def", "ghi"}.issubset(dir(fake_obj))


def test_getattr_with_annotations(fake_launchpad, mock_lplib_entry):
    class AnnotationsObject(FakeLaunchpadObject):
        some_attribute_right_here: str

    test_obj = AnnotationsObject(fake_launchpad, mock_lplib_entry)

    assert test_obj.some_attribute_right_here == str(
        mock_lplib_entry.some_attribute_right_here
    )


def test_getattr_with_callable_annotation(fake_launchpad, mock_lplib_entry):
    mock_annotation = mock.Mock()

    class AnnotationsObject(FakeLaunchpadObject):
        some_attribute_right_here: (
            mock_annotation  # pyright: ignore[reportInvalidTypeForm]
        )

    test_obj = AnnotationsObject(fake_launchpad, mock_lplib_entry)

    assert test_obj.some_attribute_right_here == mock_annotation.return_value
    mock_annotation.assert_called_once_with(mock_lplib_entry.some_attribute_right_here)


def test_getattr_with_attr_map(fake_launchpad, mock_lplib_entry):
    class AnnotationsObject(FakeLaunchpadObject):
        _attr_map = {"some_attribute_right_here": "some.attribute"}

    test_obj = AnnotationsObject(fake_launchpad, mock_lplib_entry)

    assert test_obj.some_attribute_right_here == mock_lplib_entry.some.attribute


def test_getattr_with_lp_annotations(fake_obj, mock_lplib_entry):
    mock_lplib_entry.lp_attributes = ["abcd"]

    assert fake_obj.abcd == mock_lplib_entry.abcd


def test_getattr_with_entries(fake_obj, mock_lplib_entry):
    mock_lplib_entry.lp_entries = ["aoeu"]
    with pytest.raises(NotImplementedError):
        fake_obj.aoeu  # noqa: B018


def test_getattr_with_collections(fake_obj, mock_lplib_entry):
    mock_lplib_entry.lp_collections = ["aoeu"]
    with pytest.raises(NotImplementedError):
        fake_obj.aoeu  # noqa: B018


@pytest.mark.parametrize("item", ["_lp", "_obj"])
def test_setattr_protected_attributes(fake_obj, item):
    expected = ["expected value"]

    setattr(fake_obj, item, expected)

    assert getattr(fake_obj, item) is expected
