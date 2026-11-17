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
"""Tests for Witchcraft extension support."""

from __future__ import annotations

import craft_application
from craft_application.extensions import get_extension_class, get_extension_names
from witchcraft.application import WITCHCRAFT
from witchcraft.cli import create_app, register_extensions
from witchcraft.extensions import PotionExtension
from witchcraft.services.project import ProjectService


def test_witchcraft_potion_extension_registered():
    app = create_app()
    assert "potion" in get_extension_names()
    assert get_extension_class("potion") is PotionExtension

    command_names = [cmd.name for group in app.command_groups for cmd in group.commands]
    assert "list-extensions" in command_names
    assert "expand-extensions" in command_names


def test_witchcraft_project_service_applies_extensions(tmp_path):
    register_extensions()
    project_file = tmp_path / "witchcraft.yaml"
    project_file.write_text(
        """\
name: my-witchcraft
base: ubuntu@24.04
version: "1.0"
summary: A magical test
description: Test cauldron
platforms:
  amd64:
    build-on: [amd64]
    build-for: [amd64]
extensions:
  - potion
"""
    )

    services = craft_application.ServiceFactory(app=WITCHCRAFT)
    project_service = ProjectService(
        WITCHCRAFT,
        services,
        project_dir=tmp_path,
    )
    project_service.configure(platform="amd64", build_for="amd64")

    # Render project - verify extension snippets were applied
    project_model = project_service.get()
    assert project_model.extensions == ["potion"]
    assert project_model.title == "Potion Cauldron (mystic)"
    assert "potion/brewing" in project_model.parts
    assert project_model.parts["potion/brewing"]["stage-packages"] == [
        "belladonna",
    ]
