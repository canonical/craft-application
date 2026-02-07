# This file is part of craft_application.
#
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
"""Tests for the Testcraft linter service."""

from __future__ import annotations

import importlib
import tarfile
from typing import TYPE_CHECKING, cast

import pytest
from craft_application import models
from craft_application.lint import LintContext, Stage
from craft_application.services.linter import LinterService

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from craft_application.services.service_factory import ServiceFactory


@pytest.fixture(autouse=True)
def _reset_registry() -> Iterator[None]:
    """Ensure the global linter registry does not leak between tests."""
    snapshot = {
        stage: list(classes) for stage, classes in LinterService._class_registry.items()
    }
    for registry in LinterService._class_registry.values():  # type: ignore[attr-defined]
        registry.clear()
    try:
        yield
    finally:
        LinterService._class_registry = {
            stage: list(classes) for stage, classes in snapshot.items()
        }


def _make_artifact(tmp_path: Path) -> Path:
    prime_dir = tmp_path / "prime"
    prime_dir.mkdir()
    (prime_dir / "metadata.yaml").write_text("meta")
    artifact = tmp_path / "sample.testcraft"
    with tarfile.open(artifact, mode="w:xz") as tar:
        tar.add(prime_dir, arcname=".")
    return artifact


def test_post_stage_uses_packed_artifact(tmp_path, app_metadata):
    linter_module = importlib.import_module("testcraft.services.linter")
    testcraft_linter_service = linter_module.TestcraftLinterService

    class StubPackage:
        def __init__(self, artifact_path: Path) -> None:
            self._state = models.PackState(artifact=artifact_path, resources=None)

        def read_state(self):
            return self._state

    class StubServices:
        def __init__(self, package) -> None:
            self._package = package

        def get(self, name: str):
            if name == "package":
                return self._package
            raise KeyError(name)

    artifact = _make_artifact(tmp_path)
    services = cast("ServiceFactory", StubServices(StubPackage(artifact)))
    service = testcraft_linter_service(app_metadata, services)
    context = LintContext(project_dir=tmp_path, artifact_dirs=[])

    issues = list(service.run(Stage.POST, context))

    assert any(issue.id == "TC100" for issue in issues)
