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

from datetime import date
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


@pytest.mark.skipif(
    date.today() <= date(2025, 3, 31), reason="run_managed is going away."
)
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
                # One platform, so one create/teardown
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
    monkeypatch,
    pack_args,
    expected_calls,
    expected_clean_existing,
    fake_platform,
    capsys,
):
    """Test that the application calls the correct FetchService methods."""
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services.provider = mock_provider
    app.services.get("project").set(fake_project)

    fetch_calls: list[str] = []
    app.services.register("fetch", FakeFetchService)
    app.services.update_kwargs("fetch", fetch_calls=fetch_calls)

    monkeypatch.setattr(
        "sys.argv", ["testcraft", "pack", "--platform", fake_platform, *pack_args]
    )
    build_plan_service = app.services.get("build_plan")
    build_plan_service.set_platforms(fake_platform)
    build_plan = app.services.get("build_plan").plan()

    result = app.run()

    if result != 0:  # We'll fail if the platform doesn't build on this arch.
        assert fetch_calls == []
        stdout, stderr = capsys.readouterr()
        assert "No build matches the current execution environment" in stderr
    else:
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

    assert len(instance_calls) == len(build_plan)
    for call in instance_calls:
        assert call.kwargs["clean_existing"] == expected_clean_existing
