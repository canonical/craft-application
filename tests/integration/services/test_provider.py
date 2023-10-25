#  This file is part of craft-application.
#
#  Copyright 2023 Canonical Ltd.
#
#  This program is free software: you can redistribute it and/or modify it
#  under the terms of the GNU Lesser General Public License version 3, as
#  published by the Free Software Foundation.
#
#  This program is distributed in the hope that it will be useful, but WITHOUT
#  ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
#  SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.
#  See the GNU Lesser General Public License for more details.
#
#  You should have received a copy of the GNU Lesser General Public License
#  along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Integration tests for provider service."""
import contextlib

import craft_providers
import pytest
from craft_application.models import BuildInfo
from craft_application.util import get_host_architecture
from craft_providers import bases


@pytest.mark.parametrize(
    "base_name",
    [
        pytest.param(("ubuntu", "23.10"), id="ubuntu_latest"),
        pytest.param(("ubuntu", "22.04"), id="ubuntu_lts"),
        pytest.param(("ubuntu", "20.04"), id="ubuntu_old_lts"),
        pytest.param(("almalinux", "9"), id="almalinux_9"),
    ],
)
@pytest.mark.parametrize(
    "name",
    [
        pytest.param("lxd", marks=pytest.mark.lxd),
        pytest.param("multipass", marks=pytest.mark.multipass),
    ],
)
# The LXD tests can be flaky, erroring out with a BaseCompatibilityError:
# "Clean incompatible instance and retry the requested operation."
# This is due to an upstream LXD bug that appears to still be present in LXD 5.14:
# https://github.com/lxc/lxd/issues/11422
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_provider_lifecycle(
    snap_safe_tmp_path, app_metadata, provider_service, name, base_name
):
    if name == "multipass" and base_name[0] != "ubuntu":
        pytest.skip("multipass only provides ubuntu images")
    provider_service.get_provider(name)

    arch = get_host_architecture()
    build_info = BuildInfo("foo", arch, arch, bases.BaseName(*base_name))
    instance = provider_service.instance(build_info, work_dir=snap_safe_tmp_path)
    executor = None
    try:
        with instance as executor:
            executor.execute_run(
                ["touch", str(app_metadata.managed_instance_project_path / "test")]
            )
    finally:
        if executor is not None:
            with contextlib.suppress(craft_providers.ProviderError):
                executor.delete()

    assert (snap_safe_tmp_path / "test").exists()
