# This file is part of craft_application.
#
# Copyright 2023 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Shared data for all craft-application tests."""
from __future__ import annotations

from importlib import metadata
from typing import TYPE_CHECKING

import craft_application
import craft_parts
import pytest
from craft_application import LifecycleService
from craft_cli import EmitterMode, emit

if TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Iterator


@pytest.fixture()
def app_metadata() -> craft_application.AppMetadata:
    with pytest.MonkeyPatch.context() as m:
        m.setattr(metadata, "version", lambda _: "3.14159")
        return craft_application.AppMetadata(
            "testcraft",
            "A fake app for testing craft-application",
            source_ignore_patterns=["*.snap", "*.charm", "*.starcraft"],
        )


@pytest.fixture()
def fake_project() -> craft_application.models.Project:
    return craft_application.models.Project(
        name="full-project",  # pyright: ignore[reportGeneralTypeIssues]
        title="A fully-defined project",  # pyright: ignore[reportGeneralTypeIssues]
        base="core24",
        version="1.0.0.post64+git12345678",  # pyright: ignore[reportGeneralTypeIssues]
        contact="author@project.org",
        issues="https://github.com/canonical/craft-application/issues",
        source_code="https://github.com/canonical/craft-application",  # pyright: ignore[reportGeneralTypeIssues]
        summary="A fully-defined craft-application project.",  # pyright: ignore[reportGeneralTypeIssues]
        description="A fully-defined craft-application project. (description)",
        license="LGPLv3",
        parts={"my-part": {"plugin": "nil"}},
    )


@pytest.fixture()
def enable_overlay() -> Iterator[craft_parts.Features]:
    """Enable the overlay feature in craft_parts for the relevant test."""
    craft_parts.Features.reset()
    yield craft_parts.Features(enable_overlay=True)
    craft_parts.Features.reset()


@pytest.fixture()
def lifecycle_service(app_metadata, fake_project, tmp_path) -> LifecycleService:
    work_dir = tmp_path / "work"
    cache_dir = tmp_path / "cache"

    return LifecycleService(
        app_metadata,
        fake_project,
        work_dir=work_dir,
        cache_dir=cache_dir,
    )


@pytest.fixture(params=list(EmitterMode))
def emitter_verbosity(request):
    reset_verbosity = emit.get_mode()
    emit.set_mode(request.param)
    yield request.param
    emit.set_mode(reset_verbosity)
