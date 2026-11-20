#  This file is part of craft-application.
#
#  Copyright 2026 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Unit tests for the authentication-related logic."""

import base64

from craft_application.services.sourcestore._environment import ENV_VARS


def test_auth_from_env_var(monkeypatch, fake_services):
    """Test that SourceStoreService picks up auth from environment variable."""
    credentials = "test-credentials"
    encoded_credentials = base64.b64encode(credentials.encode()).decode()
    monkeypatch.setenv(ENV_VARS.source_store_credentials, encoded_credentials)

    source_store = fake_services.get("source_store")

    auth = source_store._credential_storage
    stored_credentials = auth.get_credentials()

    assert stored_credentials == credentials
