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
from unittest import mock

import craft_providers
import pytest
from craft_application import services
from craft_application.util import get_host_architecture
from typing_extensions import override


class FakeFetchService(services.FetchService):
    """Fake FetchService that tracks calls"""

    calls: list[str]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = []

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
    def teardown_session(self) -> None:
        self.calls.append("teardown_session")

    @override
    def shutdown(self, *, force: bool = False) -> None:
        self.calls.append(f"shutdown({force})")


@pytest.mark.enable_features("fetch_service")
@pytest.mark.parametrize("fake_build_plan", [2], indirect=True)
def test_run_managed_fetch_service(app, fake_project, fake_build_plan):
    """Test that the application calls the correct FetchService methods."""
    mock_provider = mock.MagicMock(spec_set=services.ProviderService)
    app.services.provider = mock_provider
    app.project = fake_project

    expected_build_infos = 2
    assert len(fake_build_plan) == expected_build_infos
    app._build_plan = fake_build_plan

    app.services.FetchClass = FakeFetchService

    app.run_managed(None, get_host_architecture())

    fetch_service = app.services.fetch
    assert fetch_service.calls == [
        # One call to setup
        "setup",
        # Two pairs of create/teardown sessions, for two builds
        "create_session",
        "teardown_session",
        "create_session",
        "teardown_session",
        # One call to shut down (without `force`)
        "shutdown(False)",
    ]
