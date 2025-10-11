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
"""A pytest plugin for assisting in testing apps that use craft-application."""

from __future__ import annotations

import os
import pathlib
import platform
from typing import TYPE_CHECKING

import craft_platforms
import pytest
from craft_parts import callbacks

from craft_application import util
from craft_application.util import platforms

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pyfakefs.fake_filesystem import FakeFilesystem


@pytest.fixture(autouse=True, scope="session")
def debug_mode() -> None:
    """Ensure that the application is in debug mode, raising exceptions from run().

    This fixture is automatically used. To disable debug mode for specific tests,
    use the :py:func:`production_mode` fixture.
    """
    os.environ["CRAFT_DEBUG"] = "1"


@pytest.fixture
def production_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Put the application into production mode.

    This fixture puts the application into production mode rather than debug mode.
    It should only be used if the application needs to test behaviour that differs
    between debug mode and production mode.
    """
    monkeypatch.setenv("CRAFT_DEBUG", "0")


@pytest.fixture
def managed_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tell the application it's running in managed mode.

    This fixture sets up the application's environment so that it appears to be using
    managed mode. Useful for testing behaviours that only occur in managed mode.
    """
    if os.getenv("CRAFT_BUILD_ENVIRONMENT") == "host":
        raise LookupError("Managed mode and destructive mode are mutually exclusive.")
    monkeypatch.setenv(platforms.ENVIRONMENT_CRAFT_MANAGED_MODE, "1")


@pytest.fixture
def destructive_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tell the application it's running in destructive mode.

    This fixture sets up the application's environment so that it appears to be running
    in destructive mode with the "CRAFT_BUILD_ENVIRONMENT" environment variable set.
    """
    if os.getenv(platforms.ENVIRONMENT_CRAFT_MANAGED_MODE):
        raise LookupError("Destructive mode and managed mode are mutually exclusive.")
    monkeypatch.setenv("CRAFT_BUILD_ENVIRONMENT", "host")


def _optional_pyfakefs(request: pytest.FixtureRequest) -> FakeFilesystem | None:
    """Get pyfakefs if it's in use by the fixture request."""
    if {"fs", "fs_class", "fs_module", "fs_session"} & set(request.fixturenames):
        try:
            from pyfakefs.fake_filesystem import FakeFilesystem  # noqa: PLC0415

            fs = request.getfixturevalue("fs")
            if isinstance(fs, FakeFilesystem):
                return fs
        except ImportError:
            # pyfakefs isn't installed,so this fixture means something else.
            pass
    return None


@pytest.fixture(params=craft_platforms.DebianArchitecture)
def fake_host_architecture(
    request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch
) -> Iterator[craft_platforms.DebianArchitecture]:
    """Run this test as though running on each supported architecture.

    This parametrized fixture provides architecture values for all supported
    architectures, simulating running on that architecture.
    This fixture is limited to setting the architecture within this python process.
    """
    arch: craft_platforms.DebianArchitecture = request.param
    platform_arch = arch.to_platform_arch()
    real_uname = platform.uname()
    monkeypatch.setattr(
        "platform.uname", lambda: real_uname._replace(machine=platform_arch)
    )
    monkeypatch.setattr("craft_parts.infos._get_host_architecture", lambda: arch.value)
    util.get_host_architecture.cache_clear()
    yield arch
    util.get_host_architecture.cache_clear()


@pytest.fixture
def project_path(request: pytest.FixtureRequest) -> pathlib.Path:
    """Get a temporary path for a project.

    This fixture creates a temporary path for a project. It does not create any files
    in the project directory, but rather provides a pristine project directory without
    the need to worry about other fixtures loading things.

    This fixture can be used with or without pyfakefs.
    """
    if fs := _optional_pyfakefs(request):
        project_path = pathlib.Path("/test/project")
        fs.create_dir(project_path)  # type: ignore[reportUnknownMemberType]
        return project_path
    tmp_path: pathlib.Path = request.getfixturevalue("tmp_path")
    path = tmp_path / "project"
    path.mkdir()
    return path


@pytest.fixture
def in_project_path(
    project_path: pathlib.Path, monkeypatch: pytest.MonkeyPatch
) -> pathlib.Path:
    """Run the test inside the project path.

    This fixture changes the working directory of the test to use the project path.
    Best to use with ``pytest.mark.usefixtures``
    """
    monkeypatch.chdir(project_path)
    return project_path


@pytest.fixture(autouse=True)
def _reset_craft_parts_callbacks(request: pytest.FixtureRequest) -> Iterator[None]:  # pyright: ignore[reportUnusedFunction]
    """Reset craft-parts callbacks after running tests.

    This fixture resets the
    :external+craft-parts:doc:`craft-parts callbacks <reference/gen/craft_parts>`
    after running each test. Craft-application registers callbacks in several places
    and if we try to re-register them, the test will fail even though the reason is
    unrelated to the test.

    Double-registering the same callback during (or in the setup of) the same test will
    still correctly error.

    This fixture can be disabled by using the ``no_reset_craft_parts_callbacks`` mark.
    """
    yield
    if "no_reset_craft_parts_callbacks" not in request.keywords:
        callbacks.unregister_all()
