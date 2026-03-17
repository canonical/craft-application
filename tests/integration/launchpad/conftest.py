"""Configuration items for integration tests."""

import shutil

import launchpadlib.launchpad
import launchpadlib.uris
import platformdirs
import pytest
from craft_application.launchpad import Launchpad


@pytest.fixture(scope="session")
def cache_dir():
    tmp_path = platformdirs.user_runtime_path("launchpad-client-integration-tests")
    cache_dir = tmp_path / "test_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    yield cache_dir
    shutil.rmtree(cache_dir)


@pytest.fixture(scope="session")
def anonymous_lplib(cache_dir):
    """An anonymous Launchpadlib client."""
    return launchpadlib.launchpad.Launchpad.login_anonymously(
        consumer_name="integration tests for https://github.com/lengau/launchpad-client",
        service_root="production",
        launchpadlib_dir=cache_dir,
        version="devel",
    )


@pytest.fixture(scope="session")
def anonymous_lp(anonymous_lplib):
    """A Launchpad client with anonymous access."""
    return Launchpad("craft-lp-test", anonymous_lplib)
