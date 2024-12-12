# This file is part of craft_application.
#
# Copyright 2024 Canonical Ltd.
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
"""Unit tests for the interaction between the Application and the FetchService."""
from typing import Any
from unittest import mock

import craft_providers
import pytest
from typing_extensions import override

from craft_application import services


class FakeFetchService(services.FetchService):
    """Fake FetchService that tracks calls"""

    def __init__(self, *args, fetch_calls: list[str], **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = fetch_calls

    @override
    def setup(self) -> None:
        self.calls.append("setup")

    @override
    def create_session(
        self,
        instance: craft_providers.Executor,  # (unused-method-argument)
    ) -> dict[str, str]:
        self.calls.append("create_session")
        return {}

    @override
    def teardown_session(self) -> dict[str, Any]:
        self.calls.append("teardown_session")
        return {}

    @override
    def shutdown(self, *, force: bool = False) -> None:
        self.calls.append(f"shutdown({force})")


@pytest.mark.parametrize("fake_build_plan", [2], indirect=True)
@pytest.mark.parametrize(
    ("pack_args", "expected_calls", "expected_clean_existing"),
    [
        # No --enable-fetch-service: no calls to the FetchService
        (
            [],
            [],
            False,
        ),
        # --enable-fetch-service: full expected calls to the FetchService
        (
            ["--enable-fetch-service", "strict"],
            [
                # One call to setup
                "setup",
                # Two pairs of create/teardown sessions, for two builds
                "create_session",
                "teardown_session",
                "create_session",
                "teardown_session",
                # One call to shut down (with `force`)
                "shutdown(True)",
            ],
            True,
        ),
    ],
)
def test_run_managed_fetch_service(
    app,
    fake_project,
    fake_build_plan,
    monkeypatch,
    pack_args,
    expected_calls,
    expected_clean_existing,
):
    """Test that the application calls the correct FetchService methods."""
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services.provider = mock_provider
    app.set_project(fake_project)

    expected_build_infos = 2
    assert len(fake_build_plan) == expected_build_infos
    app._build_plan = fake_build_plan

    fetch_calls: list[str] = []
    app.services.register("fetch", FakeFetchService)
    app.services.update_kwargs("fetch", fetch_calls=fetch_calls)

    monkeypatch.setattr("sys.argv", ["testcraft", "pack", *pack_args])
    app.run()

    assert fetch_calls == expected_calls

    # Check that the provider service was correctly instructed to clean, or not
    # clean, the existing instance.

    # Filter out the various calls to entering and exiting the instance()
    # context manager.
    instance_calls = [
        call
        for call in mock_provider.instance.mock_calls
        if "work_dir" in call.kwargs and "clean_existing" in call.kwargs
    ]

    assert len(instance_calls) == len(fake_build_plan)
    for call in instance_calls:
        assert call.kwargs["clean_existing"] == expected_clean_existing
