# This file is part of craft-application.
#
# Copyright 2026 Canonical Ltd.
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
"""Tests for extension commands."""

from __future__ import annotations

import argparse
from textwrap import dedent
from typing import Any
from unittest import mock

import pytest
from craft_application.commands import (
    ExpandExtensionsCommand,
    ExtensionsCommand,
    ListExtensionsCommand,
    get_extensions_command_group,
)
from craft_application.extensions import Extension, register, unregister
from typing_extensions import override


class SampleExtension(Extension):
    """Sample extension for command tests."""

    name = "sample"

    @staticmethod
    @override
    def get_supported_bases() -> tuple[str, ...]:
        return ("ubuntu@22.04", "ubuntu@24.04")

    @staticmethod
    @override
    def is_experimental(base: str | None) -> bool:
        return False

    @override
    def get_root_snippet(self) -> dict[str, Any]:
        return {"title": "Expanded Sample"}

    @override
    def get_parts_snippet(self) -> dict[str, Any]:
        return {
            f"{self.extension_name}/helper": {
                "plugin": "nil",
            }
        }


@pytest.fixture
def sample_extension():
    register("sample", SampleExtension)
    yield
    unregister("sample")


def test_get_extensions_command_group():
    group = get_extensions_command_group()
    assert group.name == "Extensions"
    assert ListExtensionsCommand in group.commands
    assert ExtensionsCommand in group.commands
    assert ExpandExtensionsCommand in group.commands


@pytest.mark.parametrize("cmd_class", [ListExtensionsCommand, ExtensionsCommand])
def test_list_extensions_run(
    cmd_class, sample_extension, app_metadata, mock_services, emitter
):
    command = cmd_class({"app": app_metadata, "services": mock_services})
    command.run(argparse.Namespace())

    expected = dedent(
        """\
        Extension name  Supported bases
        --------------  --------------------------
        sample          ubuntu@22.04, ubuntu@24.04"""
    )
    emitter.assert_message(expected)


def test_expand_extensions_run(
    sample_extension, app_metadata, mock_services, tmp_path, monkeypatch, emitter
):
    project_file = tmp_path / f"{app_metadata.name}.yaml"
    project_file.write_text(
        """\
name: testcraft
base: ubuntu@24.04
extensions:
  - sample
"""
    )

    mock_project_service = mock.Mock()
    mock_project_service.resolve_project_file_path.return_value = project_file
    mock_project_service.get_raw.return_value = {
        "name": "testcraft",
        "base": "ubuntu@24.04",
        "extensions": ["sample"],
    }
    monkeypatch.setattr(
        mock_services, "get", mock.Mock(return_value=mock_project_service)
    )

    command = ExpandExtensionsCommand({"app": app_metadata, "services": mock_services})
    assert command.needs_project(argparse.Namespace()) is True
    command.run(argparse.Namespace())

    expected = dedent(
        """\
        name: testcraft
        base: ubuntu@24.04
        extensions:
        - sample
        title: Expanded Sample
        parts:
          sample/helper:
            plugin: nil
        """
    )
    emitter.assert_message(expected)
