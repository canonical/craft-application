# This file is part of craft_application.
#
# Copyright 2023 Canonical Ltd.
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
"""Integration tests for parts lifecycle."""
import os
import textwrap

import craft_cli
import pytest
import pytest_check
from craft_application.services.lifecycle import LifecycleService


@pytest.fixture(
    params=[
        pytest.param({"my-part": {"plugin": "nil"}}, id="basic"),
        pytest.param(
            {"my-part": {"plugin": "nil"}, "your-part": {"plugin": "nil"}},
            id="two-parts",
        ),
    ]
)
def parts_lifecycle(
    app_metadata, fake_project, fake_services, tmp_path, request, fake_build_plan
):
    fake_project.parts = request.param

    service = LifecycleService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=tmp_path / "work",
        cache_dir=tmp_path / "cache",
        platform=None,
        build_plan=fake_build_plan,
    )
    service.setup()
    return service


def test_run_and_clean_all_parts(parts_lifecycle, emitter, check, tmp_path):
    parts_lifecycle.run("prime")

    with check:
        emitter.assert_trace("Planning prime for all parts")

    emitter.interactions = []

    parts_lifecycle.clean()

    with check:
        emitter.assert_progress("Cleaning all parts")

    pytest_check.is_false([*(tmp_path / "work").iterdir()])


def test_run_and_clean_my_part(parts_lifecycle, emitter, check):
    parts_lifecycle.run("prime", ["my-part"])

    with check:
        emitter.assert_trace("Planning prime for ['my-part']")

    emitter.interactions = []

    parts_lifecycle.clean(["my-part"])

    with check:
        emitter.assert_progress("Cleaning parts: my-part")


def test_lifecycle_messages_no_duplicates(parts_lifecycle, request, capsys):
    if request.node.callspec.id != "basic":
        pytest.skip("Hardcoded expected output assumes 'basic' lifecycle parts.")

    craft_cli.emit.set_mode(craft_cli.EmitterMode.VERBOSE)
    parts_lifecycle.run("prime")

    _, stderr = capsys.readouterr()

    expected_output = textwrap.dedent(
        """\
        Pulling my-part
        Building my-part
        Staging my-part
        Priming my-part
        """
    )

    assert expected_output in stderr


@pytest.mark.usefixtures("enable_overlay")
def test_package_repositories_in_overlay(
    app_metadata, fake_project, fake_services, tmp_path, mocker, fake_build_plan
):
    # Mock overlay-related calls that need root; we won't be actually installing
    # any packages, just checking that the repositories are correctly installed
    # in the overlay.
    mocker.patch("craft_parts.overlays.OverlayManager.refresh_packages_list")
    mocker.patch("craft_parts.overlays.OverlayManager.download_packages")
    mocker.patch("craft_parts.overlays.OverlayManager.install_packages")
    mocker.patch.object(os, "geteuid", return_value=0)

    parts = {
        "with-overlay": {
            "plugin": "nil",
            "overlay-packages": ["hello"],
        }
    }
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    base_dir = tmp_path / "base"
    base_dir.mkdir()

    base_layer_dir = base_dir / "base"
    base_layer_dir.mkdir()

    # Create a fake Apt installation inside the base layer dir
    (base_layer_dir / "etc/apt").mkdir(parents=True)
    (base_layer_dir / "etc/apt/keyrings").mkdir()
    (base_layer_dir / "etc/apt/sources.list.d").mkdir()
    (base_layer_dir / "etc/apt/preferences.d").mkdir()

    package_repositories = [
        {"type": "apt", "ppa": "mozillateam/ppa", "priority": "always"}
    ]

    # Mock the installation of package repositories in the base system, as that
    # is undesired and will fail without root.
    mocker.patch("craft_application.util.repositories.install_package_repositories")

    fake_project.package_repositories = package_repositories
    fake_project.parts = parts
    service = LifecycleService(
        app_metadata,
        fake_services,
        project=fake_project,
        work_dir=work_dir,
        cache_dir=tmp_path / "cache",
        platform=None,
        build_plan=fake_build_plan,
        base_layer_dir=base_layer_dir,
        base_layer_hash=b"deadbeef",
    )
    service.setup()
    service.run("prime")
    # pylint: disable=protected-access
    parts_lifecycle = service._lcm

    overlay_apt = parts_lifecycle.project_info.overlay_dir / "packages/etc/apt"
    assert overlay_apt.is_dir()

    # Checking that the files are present should be enough
    pytest_check.is_true((overlay_apt / "keyrings/craft-9BE21867.gpg").is_file())
    pytest_check.is_true(
        (overlay_apt / "sources.list.d/craft-ppa-mozillateam_ppa.sources").is_file()
    )
    pytest_check.is_true((overlay_apt / "preferences.d/craft-archives").is_file())
