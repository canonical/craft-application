#  This file is part of craft-application.
#
#  Copyright 2023-2024 Canonical Ltd.
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
import subprocess

import craft_providers
import pytest
from craft_application.models import BuildInfo
from craft_application.util import get_host_architecture
from craft_providers import bases


@pytest.mark.parametrize(
    "base_name",
    [
        pytest.param(
            ("ubuntu", "24.10"),
            id="ubuntu_latest",
            marks=pytest.mark.skip(
                reason="Skipping Oracular test for now; see https://github.com/canonical/craft-providers/issues/593"
            ),
        ),
        pytest.param(("ubuntu", "24.04"), id="ubuntu_lts"),
        pytest.param(("ubuntu", "22.04"), id="ubuntu_old_lts"),
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
            proc_result = executor.execute_run(
                ["cat", "/root/.bashrc"],
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            )
    finally:
        if executor is not None:
            with contextlib.suppress(craft_providers.ProviderError):
                executor.delete()

    assert (snap_safe_tmp_path / "test").exists()
    assert proc_result.stdout.startswith("#!/bin/bash")


@pytest.mark.parametrize("base", [bases.BaseName("ubuntu", "22.04")])
@pytest.mark.parametrize(
    "proxy_vars",
    [
        {
            "http_proxy": "http://craft-application-test.local:0",
            "https_proxy": "https://craft-application-test.local:0",
            "no_proxy": "::1,127.0.0.1,0.0.0.0,canonical.com",
        },
    ],
)
@pytest.mark.parametrize("provider_name", [pytest.param("lxd", marks=pytest.mark.lxd)])
def test_proxy_variables_forwarded(
    monkeypatch, snap_safe_tmp_path, provider_service, base, proxy_vars, provider_name
):
    for var, content in proxy_vars.items():
        monkeypatch.setenv(var, content)
    arch = get_host_architecture()
    build_info = BuildInfo("foo", arch, arch, base)
    provider_service.get_provider(provider_name)
    executor = None

    provider_service.setup()
    try:
        with provider_service.instance(
            build_info, work_dir=snap_safe_tmp_path
        ) as executor:
            proc_result = executor.execute_run(
                ["env"], text=True, stdout=subprocess.PIPE, check=True
            )
    finally:
        if executor is not None:
            with contextlib.suppress(craft_providers.ProviderError):
                executor.delete()

    instance_env = {}
    for line in proc_result.stdout.splitlines():
        name, value = line.split("=", maxsplit=1)
        instance_env[name] = value

    for var, content in proxy_vars.items():
        assert instance_env.get(var) == content
