# This file is part of craft_application.
#
# Copyright 2023-2024 Canonical Ltd.
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

"""Unit tests for grammar processing (not validation)."""
from textwrap import dedent

import pytest
from craft_application import application, grammar, models, util

from tests.conftest import GRAMMAR_PACKAGE_REPOSITORIES, MyBuildPlanner

FULL_PROJECT_YAML = """
name: myproject
version: 1.0
parts:
  mypart:
    plugin: nil
    source: non-grammar-source
    source-checksum: on-amd64-to-riscv64-checksum
    source-branch: riscv64-branch
    source-commit: riscv64-commit
    source-depth: 1
    source-subdir: riscv64-subdir
    source-submodules:
      - riscv64-submodules-1
      - riscv64-submodules-2
    source-tag: riscv64-tag
    source-type: riscv64-type
    disable-parallel: true
    after:
      - riscv64-after
    organize:
      riscv64-organize-1: riscv64-organize-2
      riscv64-organize-3: riscv64-organize-4
    overlay:
      - riscv64-overlay-1
      - riscv64-overlay-2
    overlay-packages:
      - riscv64-overlay-1
      - riscv64-overlay-2
    overlay-script: riscv64-overlay-script
    stage:
      - riscv64-stage-1
      - riscv64-stage-2
    stage-snaps:
      - riscv64-snap-1
      - riscv64-snap-2
    stage-packages:
      - riscv64-package-1
      - riscv64-package-2
    prime:
      - riscv64-prime-1
      - riscv64-prime-2
    build-snaps:
      - riscv64-snap-1
      - riscv64-snap-2
    build-packages:
      - riscv64-package-1
      - riscv64-package-2
    build-environment:
      - MY_VAR: riscv64-value
      - MY_VAR2: riscv64-value2
    build-attributes:
      - rifcv64-attr-1
      - rifcv64-attr-2
    override-pull: riscv64-override-pull
    override-build: riscv64-override-build
    override-stage: riscv64-override-stage
    override-prime: riscv64-override-prime
    permissions:
      - path: riscv64-perm-1
        owner: 123
        group: 123
        mode: "777"
      - path: riscv64-perm-2
        owner: 456
        group: 456
        mode: "666"
"""

FULL_GRAMMAR_PROJECT_YAML = """
name: myproject
version: 1.0
parts:
  mypart:
    plugin:
      - on amd64 to riscv64: nil
      - on amd64 to s390x: dump
    source:
      - on amd64 to s390x: on-amd64-to-s390x
      - on amd64 to riscv64: on-amd64-to-riscv64
    source-checksum:
      - on amd64 to riscv64: on-amd64-to-riscv64-checksum
      - on amd64 to s390x: on-amd64-to-s390x-checksum
    source-branch:
      - on amd64 to s390x: s390x-branch
      - on amd64 to riscv64: riscv64-branch
    source-commit:
      - on amd64 to riscv64: riscv64-commit
      - on amd64 to s390x: s390x-commit
    source-depth:
      - on amd64 to s390x: 2
      - on amd64 to riscv64: 1
    source-subdir:
      - on amd64 to riscv64: riscv64-subdir
      - on amd64 to s390x: s390x-subdir
    source-submodules:
      - on amd64 to s390x:
          - s390x-submodules-1
          - s390x-submodules-2
      - on amd64 to riscv64:
          - riscv64-submodules-1
          - riscv64-submodules-2
    source-tag:
      - on amd64 to riscv64: riscv64-tag
      - on amd64 to s390x: s390x-tag
    source-type:
      - on amd64 to s390x: s390x-type
      - on amd64 to riscv64: riscv64-type
    disable-parallel:
      - on amd64 to riscv64: true
      - on amd64 to s390x: false
    after:
      - on amd64 to s390x:
        - s390x-after
      - on amd64 to riscv64:
        - riscv64-after
    organize:
        - on amd64 to riscv64:
            riscv64-organize-1: riscv64-organize-2
            riscv64-organize-3: riscv64-organize-4
        - on amd64 to s390x:
            s390x-organize-1: s390x-organize-2
            s390x-organize-3: s390x-organize-4
    overlay:
      - on amd64 to s390x:
        - s390x-overlay-1
        - s390x-overlay-2
      - on amd64 to riscv64:
        - riscv64-overlay-1
        - riscv64-overlay-2
    overlay-packages:
      - on amd64 to riscv64:
        - riscv64-overlay-1
        - riscv64-overlay-2
      - on amd64 to s390x:
        - s390x-overlay-1
        - s390x-overlay-2
    overlay-script:
        - on amd64 to s390x: s390x-overlay-script
        - on amd64 to riscv64: riscv64-overlay-script
    stage:
      - on amd64 to riscv64:
        - riscv64-stage-1
        - riscv64-stage-2
      - on amd64 to s390x:
        - s390x-stage-1
        - s390x-stage-2
    stage-snaps:
      - on amd64 to s390x:
        - s390x-snap-1
        - s390x-snap-2
      - on amd64 to riscv64:
        - riscv64-snap-1
        - riscv64-snap-2
    stage-packages:
      - on amd64 to riscv64:
        - riscv64-package-1
        - riscv64-package-2
      - on amd64 to s390x:
        - s390x-package-1
        - s390x-package-2
    prime:
      - on amd64 to s390x:
        - s390x-prime-1
        - s390x-prime-2
      - on amd64 to riscv64:
        - riscv64-prime-1
        - riscv64-prime-2
    build-snaps:
      - on amd64 to riscv64:
        - riscv64-snap-1
        - riscv64-snap-2
      - on amd64 to s390x:
        - s390x-snap-1
        - s390x-snap-2
    build-packages:
      - on amd64 to s390x:
        - s390x-package-1
        - s390x-package-2
      - on amd64 to riscv64:
        - riscv64-package-1
        - riscv64-package-2
    build-environment:
      - on amd64 to riscv64:
          - MY_VAR: riscv64-value
          - MY_VAR2: riscv64-value2
      - on amd64 to s390x:
          - MY_VAR: s390x-value
          - MY_VAR2: s390x-value2
    build-attributes:
      - on amd64 to s390x:
        - s390x-attr-1
        - s390x-attr-2
      - on amd64 to riscv64:
        - rifcv64-attr-1
        - rifcv64-attr-2
    override-pull:
      - on amd64 to riscv64: riscv64-override-pull
      - on amd64 to s390x: s390x-override-pull
    override-build:
      - on amd64 to s390x: s390x-override-build
      - on amd64 to riscv64: riscv64-override-build
    override-stage:
      - on amd64 to riscv64: riscv64-override-stage
      - on amd64 to s390x: s390x-override-stage
    override-prime:
      - on amd64 to s390x: s390x-override-prime
      - on amd64 to riscv64: riscv64-override-prime
    permissions:
      - on amd64 to riscv64:
        - path: riscv64-perm-1
          owner: 123
          group: 123
          mode: "777"
        - path: riscv64-perm-2
          owner: 456
          group: 456
          mode: "666"
      - on amd64 to s390x:
        - path: s390x-perm-1
          owner: 123
          group: 123
          mode: "666"
        - path: s390x-perm-2
          owner: 456
          group: 456
          mode: "777"
"""


@pytest.fixture()
def grammar_project_mini(tmp_path):
    """A project that builds on amd64 to riscv64 and s390x."""
    contents = dedent(
        """\
    name: myproject
    version: 1.0
    parts:
      mypart:
        plugin: meson

        # grammar-only string
        source:
        - on amd64 to riscv64: on-amd64-to-riscv64
        - on amd64 to s390x: on-amd64-to-s390x
        - else: other

        # list of grammar and non-grammar data
        build-packages:
        - test-package
        - on amd64 to riscv64:
          - on-amd64-to-riscv64
        - on amd64 to s390x:
          - on-amd64-to-s390x

        # non-grammar data in a non-grammar keyword
        meson-parameters:
        - foo
        - bar
    """
    )
    project_file = tmp_path / "testcraft.yaml"
    project_file.write_text(contents)


@pytest.fixture()
def non_grammar_project_full(tmp_path):
    """A project that builds on amd64 to riscv64."""
    project_file = tmp_path / "testcraft.yaml"
    project_file.write_text(FULL_PROJECT_YAML)


@pytest.fixture()
def grammar_project_full(tmp_path):
    """A project that builds on amd64 to riscv64 and s390x."""
    project_file = tmp_path / "testcraft.yaml"
    project_file.write_text(FULL_GRAMMAR_PROJECT_YAML)


@pytest.fixture()
def non_grammar_build_plan(mocker):
    """A build plan to build on amd64 to riscv64."""
    host_arch = "amd64"
    base = util.get_host_base()
    build_plan = [
        models.BuildInfo(
            "platform-riscv64",
            host_arch,
            "riscv64",
            base,
        )
    ]

    mocker.patch.object(MyBuildPlanner, "get_build_plan", return_value=build_plan)


@pytest.fixture()
def grammar_build_plan(mocker):
    """A build plan to build on amd64 to riscv64 and s390x."""
    host_arch = "amd64"
    base = util.get_host_base()
    build_plan = [
        models.BuildInfo(
            f"platform-{build_for}",
            host_arch,
            build_for,
            base,
        )
        for build_for in ("riscv64", "s390x")
    ]

    mocker.patch.object(MyBuildPlanner, "get_build_plan", return_value=build_plan)


@pytest.fixture()
def grammar_app_mini(
    tmp_path,
    grammar_project_mini,  # noqa: ARG001
    grammar_build_plan,  # noqa: ARG001
    app_metadata,
    fake_services,
):
    app = application.Application(app_metadata, fake_services)
    app.project_dir = tmp_path

    return app


@pytest.fixture()
def non_grammar_app_full(
    tmp_path,
    non_grammar_project_full,  # noqa: ARG001
    non_grammar_build_plan,  # noqa: ARG001
    app_metadata,
    fake_services,
):
    app = application.Application(app_metadata, fake_services)
    app.project_dir = tmp_path

    return app


@pytest.fixture()
def grammar_app_full(
    tmp_path,
    grammar_project_full,  # noqa: ARG001
    grammar_build_plan,  # noqa: ARG001
    app_metadata,
    fake_services,
):
    app = application.Application(app_metadata, fake_services)
    app.project_dir = tmp_path

    return app


def test_process_grammar_build_for(grammar_app_mini):
    """Test that a provided build-for is used to process the grammar."""
    project = grammar_app_mini.get_project(build_for="s390x")
    assert project.parts["mypart"]["source"] == "on-amd64-to-s390x"
    assert project.parts["mypart"]["build-packages"] == [
        "test-package",
        "on-amd64-to-s390x",
    ]


def test_process_grammar_platform(grammar_app_mini):
    """Test that a provided platform is used to process the grammar."""
    project = grammar_app_mini.get_project(platform="platform-riscv64")
    assert project.parts["mypart"]["source"] == "on-amd64-to-riscv64"
    assert project.parts["mypart"]["build-packages"] == [
        "test-package",
        "on-amd64-to-riscv64",
    ]


def test_process_grammar_non_grammar(grammar_app_mini):
    """Non-grammar keywords should not be modified."""
    project = grammar_app_mini.get_project(platform="platform-riscv64")

    assert project.parts["mypart"]["meson-parameters"] == ["foo", "bar"]


def test_process_grammar_default(grammar_app_mini):
    """Test that if nothing is provided the first BuildInfo is used by the grammar."""
    project = grammar_app_mini.get_project()
    assert project.parts["mypart"]["source"] == "on-amd64-to-riscv64"
    assert project.parts["mypart"]["build-packages"] == [
        "test-package",
        "on-amd64-to-riscv64",
    ]


def test_process_grammar_no_match(grammar_app_mini, mocker):
    """Test that if the build plan is empty, the grammar uses the host as target arch."""
    mocker.patch("craft_application.util.get_host_architecture", return_value="i386")
    project = grammar_app_mini.get_project()

    assert project.parts["mypart"]["source"] == "other"
    assert project.parts["mypart"]["build-packages"] == ["test-package"]


@pytest.mark.usefixtures("enable_overlay")
def test_process_non_grammar_full(non_grammar_app_full):
    """Test that the non-grammar project is processed correctly.

    The following fields are not included due to not able to be tested in this context:
    - parse-info
    """
    project = non_grammar_app_full.get_project()
    assert project.parts["mypart"]["plugin"] == "nil"
    assert project.parts["mypart"]["source"] == "non-grammar-source"
    assert project.parts["mypart"]["source-checksum"] == "on-amd64-to-riscv64-checksum"
    assert project.parts["mypart"]["source-branch"] == "riscv64-branch"
    assert project.parts["mypart"]["source-commit"] == "riscv64-commit"
    assert project.parts["mypart"]["source-depth"] == 1
    assert project.parts["mypart"]["source-subdir"] == "riscv64-subdir"
    assert project.parts["mypart"]["source-submodules"] == [
        "riscv64-submodules-1",
        "riscv64-submodules-2",
    ]
    assert project.parts["mypart"]["source-tag"] == "riscv64-tag"
    assert project.parts["mypart"]["source-type"] == "riscv64-type"
    assert project.parts["mypart"]["disable-parallel"] is True
    assert project.parts["mypart"]["after"] == ["riscv64-after"]
    assert project.parts["mypart"]["organize"] == {
        "riscv64-organize-1": "riscv64-organize-2",
        "riscv64-organize-3": "riscv64-organize-4",
    }
    assert project.parts["mypart"]["overlay"] == [
        "riscv64-overlay-1",
        "riscv64-overlay-2",
    ]
    assert project.parts["mypart"]["overlay-script"] == "riscv64-overlay-script"
    assert project.parts["mypart"]["stage"] == ["riscv64-stage-1", "riscv64-stage-2"]
    assert project.parts["mypart"]["stage-snaps"] == [
        "riscv64-snap-1",
        "riscv64-snap-2",
    ]
    assert project.parts["mypart"]["stage-packages"] == [
        "riscv64-package-1",
        "riscv64-package-2",
    ]
    assert project.parts["mypart"]["prime"] == ["riscv64-prime-1", "riscv64-prime-2"]
    assert project.parts["mypart"]["build-snaps"] == [
        "riscv64-snap-1",
        "riscv64-snap-2",
    ]
    assert project.parts["mypart"]["build-packages"] == [
        "riscv64-package-1",
        "riscv64-package-2",
    ]
    assert project.parts["mypart"]["build-environment"] == [
        {"MY_VAR": "riscv64-value"},
        {"MY_VAR2": "riscv64-value2"},
    ]
    assert project.parts["mypart"]["build-attributes"] == [
        "rifcv64-attr-1",
        "rifcv64-attr-2",
    ]
    assert project.parts["mypart"]["override-pull"] == "riscv64-override-pull"
    assert project.parts["mypart"]["override-build"] == "riscv64-override-build"
    assert project.parts["mypart"]["override-stage"] == "riscv64-override-stage"
    assert project.parts["mypart"]["override-prime"] == "riscv64-override-prime"
    assert project.parts["mypart"]["permissions"] == [
        {"path": "riscv64-perm-1", "owner": 123, "group": 123, "mode": "777"},
        {"path": "riscv64-perm-2", "owner": 456, "group": 456, "mode": "666"},
    ]


@pytest.mark.usefixtures("enable_overlay")
def test_process_grammar_full(grammar_app_full):
    """Test that the nearly all grammar is processed correctly.

    The following fields are not included due to not able to be tested in this context:
    - parse-info
    """
    project = grammar_app_full.get_project()
    assert project.parts["mypart"]["plugin"] == "nil"
    assert project.parts["mypart"]["source"] == "on-amd64-to-riscv64"
    assert project.parts["mypart"]["source-checksum"] == "on-amd64-to-riscv64-checksum"
    assert project.parts["mypart"]["source-branch"] == "riscv64-branch"
    assert project.parts["mypart"]["source-commit"] == "riscv64-commit"
    assert project.parts["mypart"]["source-depth"] == 1
    assert project.parts["mypart"]["source-subdir"] == "riscv64-subdir"
    assert project.parts["mypart"]["source-submodules"] == [
        "riscv64-submodules-1",
        "riscv64-submodules-2",
    ]
    assert project.parts["mypart"]["source-tag"] == "riscv64-tag"
    assert project.parts["mypart"]["source-type"] == "riscv64-type"
    assert project.parts["mypart"]["disable-parallel"] is True
    assert project.parts["mypart"]["after"] == ["riscv64-after"]
    assert project.parts["mypart"]["organize"] == {
        "riscv64-organize-1": "riscv64-organize-2",
        "riscv64-organize-3": "riscv64-organize-4",
    }
    assert project.parts["mypart"]["overlay"] == [
        "riscv64-overlay-1",
        "riscv64-overlay-2",
    ]
    assert project.parts["mypart"]["overlay-script"] == "riscv64-overlay-script"
    assert project.parts["mypart"]["stage"] == ["riscv64-stage-1", "riscv64-stage-2"]
    assert project.parts["mypart"]["stage-snaps"] == [
        "riscv64-snap-1",
        "riscv64-snap-2",
    ]
    assert project.parts["mypart"]["stage-packages"] == [
        "riscv64-package-1",
        "riscv64-package-2",
    ]
    assert project.parts["mypart"]["prime"] == ["riscv64-prime-1", "riscv64-prime-2"]
    assert project.parts["mypart"]["build-snaps"] == [
        "riscv64-snap-1",
        "riscv64-snap-2",
    ]
    assert project.parts["mypart"]["build-packages"] == [
        "riscv64-package-1",
        "riscv64-package-2",
    ]
    assert project.parts["mypart"]["build-environment"] == [
        {"MY_VAR": "riscv64-value"},
        {"MY_VAR2": "riscv64-value2"},
    ]
    assert project.parts["mypart"]["build-attributes"] == [
        "rifcv64-attr-1",
        "rifcv64-attr-2",
    ]
    assert project.parts["mypart"]["override-pull"] == "riscv64-override-pull"
    assert project.parts["mypart"]["override-build"] == "riscv64-override-build"
    assert project.parts["mypart"]["override-stage"] == "riscv64-override-stage"
    assert project.parts["mypart"]["override-prime"] == "riscv64-override-prime"
    assert project.parts["mypart"]["permissions"] == [
        {"path": "riscv64-perm-1", "owner": 123, "group": 123, "mode": "777"},
        {"path": "riscv64-perm-2", "owner": 456, "group": 456, "mode": "666"},
    ]


def test_process_grammar_package_repositories():
    project = util.safe_yaml_load(GRAMMAR_PACKAGE_REPOSITORIES)

    grammar.process_project(yaml_data=project, arch="amd64", target_arch="riscv64")

    apt_repo = project["package-repositories"][0]
    assert apt_repo["architectures"] == ["amd64", "i386"]
    assert apt_repo["components"] == ["main", "restricted"]
    assert apt_repo["key-server"] == "keyserver.ubuntu.com"
    assert apt_repo["url"] == "on-amd.to-riscv.com"
    assert apt_repo["suites"] == ["xenial"]
    assert apt_repo["formats"] == ["deb", "deb-src"]

    ppa_repo = project["package-repositories"][1]
    assert ppa_repo["ppa"] == "snappy-dev/snapcraft-daily"

    uca_repo = project["package-repositories"][2]
    assert uca_repo["cloud"] == "antelope"
    assert uca_repo["pocket"] == "proposed"
