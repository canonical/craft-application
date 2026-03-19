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
import pathlib
import subprocess

import craft_platforms
import craft_providers
import pytest
from craft_application import AppMetadata, ProviderService
from craft_application.services import provider as provider_module


@pytest.mark.parametrize(
    "base_name",
    [
        pytest.param(craft_platforms.DistroBase("ubuntu", "24.04"), id="ubuntu@24.04"),
        pytest.param(craft_platforms.DistroBase("ubuntu", "22.04"), id="ubuntu@22.04"),
        pytest.param(craft_platforms.DistroBase("almalinux", "9"), id="almalinux@9"),
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
# https://github.com/canonical/lxd/issues/11422
@pytest.mark.flaky(reruns=3, reruns_delay=2)
@pytest.mark.slow
def test_provider_lifecycle(
    snap_safe_tmp_path, app_metadata, provider_service, state_service, name, base_name
):
    """Set up an instance and allow write access to the project and state directories."""
    if name == "multipass" and base_name.distribution != "ubuntu":
        pytest.skip("multipass only provides ubuntu images")
    provider_service.get_provider(name)

    arch = craft_platforms.DebianArchitecture.from_host()
    build_info = craft_platforms.BuildInfo("foo", arch, arch, base_name)
    instance = provider_service.instance(build_info, work_dir=snap_safe_tmp_path)
    executor = None
    try:
        with instance as executor:
            # the provider service must allow writes in the state service directory
            executor.execute_run(
                ["touch", f"{state_service._managed_state_dir}/test.txt"],
                check=True,
            )
            executor.execute_run(
                ["touch", str(app_metadata.managed_instance_project_path / "test")],
                check=True,
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


@pytest.mark.parametrize("base", [craft_platforms.DistroBase("ubuntu", "22.04")])
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
@pytest.mark.slow
def test_proxy_variables_forwarded(
    monkeypatch, snap_safe_tmp_path, provider_service, base, proxy_vars, provider_name
):
    for var, content in proxy_vars.items():
        monkeypatch.setenv(var, content)
    arch = craft_platforms.DebianArchitecture.from_host()
    build_info = craft_platforms.BuildInfo("foo", arch, arch, base)
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


@pytest.mark.slow
@pytest.mark.parametrize("fetch", [False, True])
def test_run_managed(provider_service, fake_services, fetch, snap_safe_tmp_path):
    base = craft_platforms.DistroBase("ubuntu", "24.04")
    arch = craft_platforms.DebianArchitecture.from_host()
    build_info = craft_platforms.BuildInfo("foo", arch, arch, base)

    fetch_service = fake_services.get("fetch")
    fetch_service.set_policy("permissive")

    provider_service._work_dir = snap_safe_tmp_path

    provider_service.run_managed(
        build_info, enable_fetch_service=fetch, command=["echo", "hi"]
    )


@pytest.mark.slow
@pytest.mark.parametrize(
    "build_on",
    [
        pytest.param(
            "riscv64",
            marks=pytest.mark.skipif(
                craft_platforms.DebianArchitecture.from_host()
                == craft_platforms.DebianArchitecture.RISCV64,
                reason="Not testing on compatible host.",
            ),
        ),
        pytest.param(
            "s390x",
            marks=pytest.mark.skipif(
                craft_platforms.DebianArchitecture.from_host()
                == craft_platforms.DebianArchitecture.S390X,
                reason="Not testing on compatible host.",
            ),
        ),
    ],
)
@pytest.mark.parametrize("base", [craft_platforms.DistroBase("ubuntu", "26.04")])
def test_get_incompatible_instance_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    provider_service: ProviderService,
    build_on: str,
    base: craft_platforms.DistroBase,
):
    monkeypatch.setenv("CRAFT_BUILD_ON", build_on)

    build_info = craft_platforms.BuildInfo(
        platform="foo",
        build_on=craft_platforms.DebianArchitecture(build_on),
        build_for=craft_platforms.DebianArchitecture.from_host(),
        build_base=base,
    )

    with pytest.raises(
        craft_providers.errors.ProviderError,
        match="Requested architecture isn't supported by this host",
    ):
        with provider_service.instance(build_info, work_dir=tmp_path):
            pass


@pytest.mark.slow
@pytest.mark.parametrize(
    "build_on",
    [
        pytest.param(
            "armhf",
            marks=pytest.mark.skipif(
                craft_platforms.DebianArchitecture.from_host()
                != craft_platforms.DebianArchitecture.ARM64,
                reason="Skipping incompatible host.",
            ),
        ),
    ],
)
@pytest.mark.parametrize("base", [craft_platforms.DistroBase("ubuntu", "26.04")])
def test_instance_with_different_architecture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
    provider_service: ProviderService,
    build_on: str,
    base: craft_platforms.DistroBase,
):
    monkeypatch.setenv("CRAFT_BUILD_ON", build_on)

    build_info = craft_platforms.BuildInfo(
        platform="foo",
        build_on=craft_platforms.DebianArchitecture(build_on),
        build_for=craft_platforms.DebianArchitecture.from_host(),
        build_base=base,
    )

    with provider_service.instance(build_info, work_dir=tmp_path) as instance:
        result = instance.execute_run(
            ["dpkg", "--print-architecture"], text=True, capture_output=True
        )

    assert result.stdout.rstrip() == build_on


def _get_store_revision(snap_name: str, channel: str) -> int:
    """Get the revision of a snap published in a specific channel from the store.

    :param snap_name: The name of the snap to query.
    :param channel: The channel to query (e.g. ``"latest/stable"``).
    :returns: The revision number published in that channel.
    :raises pytest.skip.Exception: If the channel is not available in the store.
    """
    result = subprocess.run(
        ["snap", "info", "--unicode=never", snap_name],
        capture_output=True,
        text=True,
        check=True,
    )
    for line in result.stdout.splitlines():
        stripped = line.strip()
        if stripped.startswith(f"{channel}:"):
            # e.g. "latest/stable:    1.17.2    2026-03-12 (4238) 94MB classic"
            for part in stripped.split():
                if part.startswith("(") and part.endswith(")"):
                    return int(part[1:-1])
    pytest.skip(f"Channel {channel!r} is not available for snap {snap_name!r}")


@pytest.mark.parametrize(
    "channel",
    [
        pytest.param("latest/stable", id="stable"),
        pytest.param("latest/candidate", id="candidate"),
        pytest.param("latest/beta", id="beta"),
        pytest.param("latest/edge", id="edge"),
    ],
)
@pytest.mark.lxd
@pytest.mark.slow
@pytest.mark.flaky(reruns=3, reruns_delay=2)
def test_rockcraft_channel_install(
    monkeypatch: pytest.MonkeyPatch,
    snap_safe_tmp_path: pathlib.Path,
    fake_services,
    channel: str,
):
    """Test that each rockcraft channel installs the correct version in the container.

    Verifies the full provider service flow: the channel is read from
    ``CRAFT_SNAP_CHANNEL``, passed to the snap installer, and the version of
    rockcraft found inside the container matches what the snap store reports
    for that channel.
    """
    expected_revision = _get_store_revision("rockcraft", channel)

    monkeypatch.setenv("CRAFT_SNAP_CHANNEL", channel)
    rockcraft_metadata = AppMetadata("rockcraft", "Rockcraft")

    service = provider_module.ProviderService(
        rockcraft_metadata,
        fake_services,
        work_dir=snap_safe_tmp_path,
        install_snap=True,
    )
    service.setup()
    service.get_provider("lxd")

    base_name = craft_platforms.DistroBase("ubuntu", "24.04")
    arch = craft_platforms.DebianArchitecture.from_host()
    build_info = craft_platforms.BuildInfo("foo", arch, arch, base_name)

    executor = None
    try:
        with service.instance(build_info, work_dir=snap_safe_tmp_path) as executor:
            result = executor.execute_run(
                ["snap", "list", "rockcraft"],
                text=True,
                stdout=subprocess.PIPE,
                check=True,
            )
    finally:
        if executor is not None:
            with contextlib.suppress(craft_providers.ProviderError):
                executor.delete()

    # Parse `snap list` output:  Name  Version  Rev  Tracking  Publisher  Notes
    lines = result.stdout.strip().splitlines()
    assert len(lines) >= 2, f"Unexpected snap list output:\n{result.stdout}"
    installed_revision = int(lines[1].split()[2])

    assert installed_revision == expected_revision, (
        f"Channel {channel!r}: expected revision {expected_revision!r} from the store "
        f"but got {installed_revision!r} inside the container"
    )
