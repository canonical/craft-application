# Copyright 2025 Canonical Ltd.
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
"""Integration tests for the StateService."""

import pathlib

import pytest
from craft_application.services.state import StateService


@pytest.fixture
def service(app_metadata, fake_services, in_project_path: pathlib.Path):
    return StateService(app=app_metadata, services=fake_services)


def test_simple(service: StateService):
    """Simple test to set and retrieve values from the StateService."""
    service.set("artifact", "platform1", value=["artifact-1.txt", "artifact-2.txt"])

    # test all types
    service.set("test", "A", value="hello")
    service.set("test", "B", value=100)
    service.set("test", "C", value=True)
    service.set("test", "D", value=["hello world"])
    service.set("test", "E", value=None)

    assert service.get("artifact", "platform1") == ["artifact-1.txt", "artifact-2.txt"]
    assert service.get("artifact") == {
        "platform1": ["artifact-1.txt", "artifact-2.txt"]
    }

    assert service.get("test", "A") == "hello"
    assert service.get("test", "B") == 100
    assert service.get("test", "C") is True
    assert service.get("test", "D") == ["hello world"]
    assert service.get("test", "E") is None

    # test overwriting
    service.set("test", "A", value="new-value", overwrite=True)

    assert service.get("test", "A") == "new-value"
