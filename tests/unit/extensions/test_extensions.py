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
"""Tests for extension mechanism."""

from __future__ import annotations

from typing import Any

import pytest
from craft_application import errors, models
from craft_application.extensions import (
    Extension,
    apply_extensions,
    get_extension_class,
    get_extension_names,
    get_extensions,
    register,
    unregister,
)
from typing_extensions import override


class DummyExtension(Extension):
    """Dummy extension for testing."""

    name = "dummy"

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
        return {"title": "Configured Dummy"}

    @override
    def get_part_snippet(
        self,
        *,
        part_name: str | None = None,
        plugin_name: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {"stage-packages": ["dummy-lib"]}

    @override
    def get_parts_snippet(self) -> dict[str, Any]:
        return {
            f"{self.name}/helper": {
                "plugin": "nil",
                "stage-packages": ["helper-pkg"],
            }
        }


class AnotherExtension(Extension):
    """Another extension for testing order."""

    name = "another"

    @staticmethod
    @override
    def get_supported_bases() -> tuple[str, ...]:
        return ("ubuntu@24.04",)

    @staticmethod
    @override
    def is_experimental(base: str | None) -> bool:
        return False

    @override
    def get_part_snippet(
        self,
        *,
        part_name: str | None = None,
        plugin_name: str | None = None,
        **kwargs: Any,
    ) -> dict[str, Any]:
        return {"stage-packages": ["another-lib"]}


class ExperimentalExtension(Extension):
    """Experimental extension for testing."""

    name = "experimental"

    @staticmethod
    @override
    def get_supported_bases() -> tuple[str, ...]:
        return ("ubuntu@24.04",)

    @staticmethod
    @override
    def is_experimental(base: str | None) -> bool:
        return True


@pytest.fixture
def clean_registry():
    register("dummy", DummyExtension)
    register("another", AnotherExtension)
    register("experimental", ExperimentalExtension)
    yield
    if "dummy" in get_extension_names():
        unregister("dummy")
    if "another" in get_extension_names():
        unregister("another")
    if "experimental" in get_extension_names():
        unregister("experimental")


def test_registry(clean_registry):
    assert "dummy" in get_extension_names()
    assert get_extension_class("dummy") is DummyExtension

    meta = get_extensions()
    dummy_meta = next(m for m in meta if m["name"] == "dummy")
    assert dummy_meta["bases"] == ["ubuntu@22.04", "ubuntu@24.04"]
    assert dummy_meta["experimental"] is False


def test_registry_missing():
    with pytest.raises(
        errors.ExtensionError, match="Extension 'nonexistent' does not exist"
    ):
        get_extension_class("nonexistent")


def test_project_model_has_extensions():
    assert "extensions" in models.Project.model_fields


def test_apply_extensions_success(clean_registry, tmp_path):
    project_data = {
        "base": "ubuntu@24.04",
        "extensions": ["dummy"],
        "parts": {
            "my-part": {
                "plugin": "nil",
                "stage-packages": ["existing-pkg"],
            }
        },
    }

    result = apply_extensions(
        tmp_path,
        project_data,
        extensions=project_data["extensions"],
        app_name="testcraft",
    )

    assert result["extensions"] == ["dummy"]
    assert result["title"] == "Configured Dummy"
    assert result["parts"]["my-part"]["stage-packages"] == ["dummy-lib", "existing-pkg"]
    assert "dummy/helper" in result["parts"]
    assert result["parts"]["dummy/helper"]["stage-packages"] == ["helper-pkg"]


def test_apply_extensions_preserves_order(clean_registry, tmp_path):
    project_data_1 = {
        "base": "ubuntu@24.04",
        "parts": {"part1": {"plugin": "nil", "stage-packages": ["user-lib"]}},
    }
    apply_extensions(
        tmp_path,
        project_data_1,
        extensions=["dummy", "another"],
        app_name="testcraft",
    )
    # dummy runs first (prepends dummy-lib), then another runs (prepends another-lib)
    assert project_data_1["parts"]["part1"]["stage-packages"] == [
        "another-lib",
        "dummy-lib",
        "user-lib",
    ]

    project_data_2 = {
        "base": "ubuntu@24.04",
        "parts": {"part1": {"plugin": "nil", "stage-packages": ["user-lib"]}},
    }
    apply_extensions(
        tmp_path,
        project_data_2,
        extensions=["another", "dummy"],
        app_name="testcraft",
    )
    # another runs first (prepends another-lib), then dummy runs (prepends dummy-lib)
    assert project_data_2["parts"]["part1"]["stage-packages"] == [
        "dummy-lib",
        "another-lib",
        "user-lib",
    ]


def test_apply_extensions_items_not_strings_error(clean_registry, tmp_path):
    project_data = {
        "base": "ubuntu@24.04",
    }

    with pytest.raises(
        errors.ExtensionError,
        match="Extension name 123 must be a string",
    ):
        apply_extensions(
            tmp_path,
            project_data,
            extensions=[123],  # ty: ignore[invalid-argument-type]  # pyright: ignore[reportArgumentType]
            app_name="testcraft",
        )


def test_apply_extensions_unsupported_base(clean_registry, tmp_path):
    project_data = {
        "base": "ubuntu@20.04",
    }

    with pytest.raises(
        errors.ExtensionError,
        match="Extension 'dummy' does not support base 'ubuntu@20.04'",
    ):
        apply_extensions(
            tmp_path,
            project_data,
            extensions=["dummy"],
            app_name="testcraft",
        )


def test_apply_extensions_experimental_blocked(clean_registry, tmp_path, monkeypatch):
    monkeypatch.delenv("TESTCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS", raising=False)
    monkeypatch.delenv("CRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS", raising=False)

    project_data = {
        "base": "ubuntu@24.04",
    }

    with pytest.raises(
        errors.ExtensionError,
        match="Extension 'experimental' is experimental on base 'ubuntu@24.04'",
    ):
        apply_extensions(
            tmp_path,
            project_data,
            extensions=["experimental"],
            app_name="testcraft",
        )


def test_apply_extensions_experimental_allowed(clean_registry, tmp_path, monkeypatch):
    monkeypatch.setenv("TESTCRAFT_ENABLE_EXPERIMENTAL_EXTENSIONS", "1")

    project_data = {
        "base": "ubuntu@24.04",
        "extensions": ["experimental"],
    }

    result = apply_extensions(
        tmp_path,
        project_data,
        extensions=project_data["extensions"],
        app_name="testcraft",
    )
    assert result["extensions"] == ["experimental"]


def test_registry_lazy_load():
    register("potion", "PotionExtension", module="witchcraft.extensions")
    try:
        assert "potion" in get_extension_names()
        ext_cls = get_extension_class("potion")
        assert ext_cls.__name__ == "PotionExtension"
    finally:
        unregister("potion")


def test_registry_invalid_args():
    with pytest.raises(KeyError, match="Must set module"):
        register("lazy", "SomeClass")

    with pytest.raises(KeyError, match="Must not set module"):
        register("direct", DummyExtension, module="some.module")


def test_invalid_part_names(clean_registry, tmp_path):
    class BadPartExtension(Extension):
        name = "bad"

        @staticmethod
        def get_supported_bases():
            return ()

        @staticmethod
        def is_experimental(base):
            return False

        def get_parts_snippet(self):
            return {"bad-part-name": {"plugin": "nil"}}

    register("bad", BadPartExtension)
    try:
        project_data = {}
        with pytest.raises(
            errors.ExtensionError,
            match="defines invalid part names",
        ):
            apply_extensions(
                tmp_path,
                project_data,
                extensions=["bad"],
                app_name="testcraft",
            )
    finally:
        unregister("bad")
